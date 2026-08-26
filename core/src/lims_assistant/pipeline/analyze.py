"""Analyse-Orchestrierung: Quellen -> Fragmente -> fuenf Felder je Zeile.

Deterministische Pipeline vor und nach dem Modell:
Quellparser -> OCR -> Segmentierung -> Merkmalsextraktion -> Retrieval/ML ->
lokales Sprachmodell (nur wo noetig) -> Normalisierung -> Schema-Pruefung ->
Confidence/gelbe Markierung.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from lims_assistant.config import Settings
from lims_assistant.contracts.models import (
    AnalyzePayload,
    AnalyzeResult,
    AnalyzeStats,
    FieldValue,
    ResultRow,
)
from lims_assistant.domain.entities import FIELDS
from lims_assistant.fusion.fuse import fuse_row
from lims_assistant.ingest.base import IngestedDocument
from lims_assistant.ingest.excel_ingest import ingest_excel
from lims_assistant.ingest.image_ingest import ingest_image_set
from lims_assistant.ingest.pdf_ingest import ingest_pdf
from lims_assistant.learn.service import LearningService, row_signature
from lims_assistant.llm.base import LlmRowTask
from lims_assistant.normalize.compose import compose_all
from lims_assistant.ocr.base import get_engine
from lims_assistant.pipeline.zusatz import hint_fields
from lims_assistant.store import repo
from lims_assistant.version import LEARNER_VERSION, NORMALIZER_VERSION


class AnalyzeCancelled(RuntimeError):
    pass


def _noop_progress(phase: str, percent: int, message: str) -> None:
    return None


def run_analyze(
    con: sqlite3.Connection,
    settings: Settings,
    payload: AnalyzePayload,
    *,
    llm_adapter=None,
    progress=_noop_progress,
    cancelled=lambda: False,
) -> AnalyzeResult:
    started = time.monotonic()

    def check_cancel() -> None:
        if cancelled():
            raise AnalyzeCancelled("Analyse abgebrochen")

    learning = LearningService(con)
    threshold = (
        payload.options.certainty_threshold
        if payload.options.certainty_threshold is not None
        else settings.certainty_threshold
    )
    ocr_cfg = settings.ocr
    if payload.options.ocr_engine != "auto":
        from dataclasses import replace

        ocr_cfg = replace(ocr_cfg, engine=payload.options.ocr_engine)
    engine = get_engine(ocr_cfg)

    llm_enabled = (
        payload.options.llm != "off"
        and llm_adapter is not None
        and llm_adapter.available()[0]
    )

    warnings: list[str] = []
    stats = AnalyzeStats()
    hint = payload.hint_text or ""
    hints = hint_fields(hint)

    progress("import", 2, "Import wird vorbereitet")
    check_cancel()

    with con:  # eine Transaktion: kein Teilergebnis bei Fehler/Abbruch
        if payload.session_id:
            session_row = repo.get_session(con, payload.session_id)
            if session_row is None:
                raise ValueError(f"Unbekannte Session: {payload.session_id}")
            session_id = payload.session_id
            repo.append_session_hint(con, session_id, hint)
        else:
            session_id = repo.create_session(con, hint)

        result_rows: list[ResultRow] = []
        total_sources = len(payload.sources)

        for src_index, source in enumerate(payload.sources, start=1):
            check_cancel()
            base_percent = 5 + int(70 * (src_index - 1) / total_sources)
            progress(
                "import",
                base_percent,
                f"Quelle {src_index}/{total_sources} wird gelesen",
            )
            first_path = Path(source.paths[0])
            if source.type == "pdf":
                doc = ingest_pdf(
                    first_path,
                    settings=settings,
                    ocr_engine=engine,
                    pages=source.pages,
                    row_probability=learning.row_probability,
                )
            elif source.type == "image_set":
                doc = ingest_image_set(
                    [Path(p) for p in source.paths],
                    settings=settings,
                    ocr_engine=engine,
                    row_probability=learning.row_probability,
                )
            elif source.type == "excel":
                sheets = source.sheets or []
                if not sheets:
                    from lims_assistant.ingest.excel_ingest import list_sheets

                    infos, _, _ = list_sheets(first_path)
                    visible = [s.name for s in infos if s.visible]
                    if len(visible) == 1:
                        sheets = visible
                    else:
                        raise ValueError(
                            "Excel-Quelle mit mehreren Blaettern: bitte Blattauswahl treffen"
                        )
                doc = ingest_excel(
                    first_path, sheets=sheets, row_probability=learning.row_probability
                )
            else:  # pragma: no cover - Contract verhindert das
                raise ValueError(f"Unbekannter Quelltyp: {source.type}")

            warnings.extend(f"{doc.filename}: {w}" for w in doc.warnings)
            stats.documents += 1
            stats.ocr_pages += doc.ocr_pages

            repo.set_session_export_dir(con, session_id, str(first_path.resolve().parent))
            doc_id = repo.add_document(
                con,
                session_id,
                doc_type=doc.doc_type,
                filename=doc.filename,
                sha256=doc.sha256,
                extracted_text=doc.extracted_text,
                hint_text=hint,
                page_selection=doc.page_selection,
                sheet_selection=doc.sheet_selection,
            )

            seg = doc.segment
            for rej in seg.rejected:
                repo.add_fragment(
                    con,
                    doc_id,
                    page_or_sheet=rej.page_or_sheet,
                    frag_order=rej.frag_order,
                    text=rej.source_text,
                    kind="line",
                )
            stats.fragments += len(seg.rejected) + len(seg.rows)

            check_cancel()
            progress("analyse", base_percent + 8, f"{doc.filename}: Zeilen werden analysiert")

            # ---------------- LLM-Vorschlaege (nur wo noetig, gebuendelt)
            llm_by_row: dict[int, dict[str, str]] = {}
            if llm_enabled and seg.rows:
                tasks: list[LlmRowTask] = []
                composed_cache: list[dict] = []
                for i, srow in enumerate(seg.rows):
                    composed = compose_all(srow.features)
                    composed_cache.append(composed)
                    missing = [
                        f
                        for f in ("Bez2", "B3", "B4", "Untersuchungsart")
                        if not composed[f].value
                    ]
                    if missing:
                        tasks.append(
                            LlmRowTask(
                                row_ref=i,
                                source_text=srow.source_text,
                                bez1_context=srow.bez1_context.value,
                                missing_fields=missing,
                                current={
                                    f: composed[f].value
                                    for f in FIELDS
                                    if composed[f].value
                                },
                            )
                        )
                if tasks:
                    try:
                        suggestions = llm_adapter.suggest(tasks)
                    except TypeError:
                        suggestions = llm_adapter.suggest(tasks)
                    for s in suggestions:
                        llm_by_row[s.row_ref] = s.fields
                    stats.llm_rows += len(llm_by_row)
            else:
                composed_cache = [compose_all(srow.features) for srow in seg.rows]

            # ---------------- Zeilen fusionieren und persistieren
            for i, srow in enumerate(seg.rows):
                check_cancel()
                composed = composed_cache[i]
                signature = row_signature(srow.source_text, srow.bez1_context.value)
                retrieval: dict[str, tuple[str, float]] = {}
                for fname in FIELDS:
                    hits = learning.retrieve(
                        fname, signature, top_k=settings.retrieval_top_k
                    )
                    if hits and hits[0].similarity >= settings.retrieval_min_similarity:
                        retrieval[fname] = (hits[0].value, hits[0].similarity)

                decisions = fuse_row(
                    composed=composed,
                    bez1_context_value=srow.bez1_context.value,
                    bez1_context_kind=srow.bez1_context.kind,
                    retrieval=retrieval,
                    llm_fields=llm_by_row.get(i),
                    hint_fields=hints,
                    doc_untersuchung=seg.doc_context.untersuchung,
                    ocr_score=srow.ocr_score,
                    threshold=threshold,
                    ocr_min_confidence=settings.ocr.min_confidence,
                )

                frag_id = repo.add_fragment(
                    con,
                    doc_id,
                    page_or_sheet=srow.page_or_sheet,
                    frag_order=srow.frag_order,
                    text=srow.source_text,
                    kind="row",
                    ocr_score=srow.ocr_score,
                )
                source_order = repo.next_source_order(con, session_id)
                row_id = repo.add_row(
                    con,
                    session_id,
                    source_order=source_order,
                    origin="auto",
                    fragment_id=frag_id,
                    source_signature=signature,
                    bez1_context=srow.bez1_context.value,
                )
                fields_payload: dict[str, FieldValue] = {}
                for fname in FIELDS:
                    d = decisions[fname]
                    field_id = repo.set_field(
                        con,
                        row_id,
                        fname,
                        value=d.value,
                        is_uncertain=d.is_uncertain,
                        provenance=d.provenance,
                    )
                    for cand in d.candidates:
                        repo.add_proposal(
                            con,
                            field_id,
                            value=cand.value,
                            provenance=cand.provenance,
                            score=cand.score,
                            component_scores={"detail": cand.detail},
                            model_version=LEARNER_VERSION,
                            normalizer_version=NORMALIZER_VERSION,
                            is_uncertain=d.is_uncertain,
                        )
                    fields_payload[fname] = FieldValue(
                        value=d.value, is_uncertain=d.is_uncertain
                    )
                result_rows.append(
                    ResultRow(
                        row_id=row_id, source_order=source_order, fields=fields_payload
                    )
                )
                stats.rows += 1

        session_row = repo.get_session(con, session_id)
        export_dir = session_row["export_base_dir"] if session_row else ""

    if not result_rows:
        warnings.append(
            "Keine Probenstellen erkannt. Die Ergebnisliste bleibt unveraendert - "
            "bitte Dokument pruefen oder Zeilen manuell hinzufuegen."
        )

    progress("fertig", 100, f"{stats.rows} Probenstellen uebernommen")
    stats.duration_ms = int((time.monotonic() - started) * 1000)
    return AnalyzeResult(
        session_id=session_id,
        export_base_dir=export_dir,
        rows=result_rows,
        warnings=warnings,
        stats=stats,
    )

"""Lerndienst: Ereignisse -> Beispiele -> reproduzierbare Indizes.

Lernsignale (Spezifikation Kap. 10.3):
- Zellkorrektur: sofortiges Beispiel alt->neu fuer genau dieses Feld.
- Loeschen einer automatisch erkannten Zeile: negatives Zeilenbeispiel.
- Manuell hinzugefuegte Zeile: positiv erst bei Copy/Export.
- Copy/Export: bestaetigt exakt den kopierten/exportierten Umfang.
- Idempotenz ueber Deduplizierungsschluessel; Undo deaktiviert Beispiele
  und baut betroffene Indizes neu.
"""

from __future__ import annotations

import json
import sqlite3

from lims_assistant.domain.entities import FIELDS
from lims_assistant.learn.index import TfIdfIndex
from lims_assistant.learn.rowclf import RowClassifier
from lims_assistant.store import repo
from lims_assistant.textutil import fold_for_match, sanitize_lims_value


def row_signature(source_text: str, bez1_context: str = "") -> str:
    """Merkmalskette einer Zeile fuer Lernbeispiele und Retrieval."""
    base = fold_for_match(source_text)
    ctx = fold_for_match(bez1_context)
    return f"{base} || ctx {ctx}" if ctx else base


def field_signature_from_values(values: dict[str, str], exclude: str) -> str:
    """Fallback-Signatur fuer manuell angelegte Zeilen ohne Quelltext."""
    parts = [sanitize_lims_value(values.get(f, "")) for f in FIELDS if f != exclude]
    return fold_for_match(" | ".join(p for p in parts if p))


class RetrievedCase:
    __slots__ = ("example_id", "value", "similarity")

    def __init__(self, example_id: str, value: str, similarity: float) -> None:
        self.example_id = example_id
        self.value = value
        self.similarity = similarity


class LearningService:
    def __init__(self, con: sqlite3.Connection) -> None:
        self.con = con
        self._field_indexes: dict[str, TfIdfIndex] = {}
        self._row_clf: RowClassifier | None = None

    # ------------------------------------------------------------ Aufbau

    def invalidate(self) -> None:
        self._field_indexes = {}
        self._row_clf = None

    def _index_for(self, field: str) -> TfIdfIndex:
        idx = self._field_indexes.get(field)
        if idx is None:
            idx = TfIdfIndex()
            rows = repo.active_examples(self.con, "field", field)
            idx.build([(r["id"], r["input_signature"], r["label"]) for r in rows])
            self._field_indexes[field] = idx
        return idx

    def row_classifier(self) -> RowClassifier:
        if self._row_clf is None:
            clf = RowClassifier()
            rows = repo.active_examples(self.con, "row")
            clf.build([(r["input_signature"], r["label"]) for r in rows])
            self._row_clf = clf
        return self._row_clf

    def row_probability(self, text: str) -> float | None:
        return self.row_classifier().probability(fold_for_match(text))

    # ------------------------------------------------------------ Retrieval

    def retrieve(self, field: str, signature: str, top_k: int = 5) -> list[RetrievedCase]:
        idx = self._index_for(field)
        return [
            RetrievedCase(doc_id, label, sim)
            for doc_id, label, sim in idx.query(signature, top_k=top_k)
        ]

    # ------------------------------------------------------------ Ereignisse

    def on_revision(
        self,
        *,
        session_id: str,
        row: sqlite3.Row,
        field: str,
        new_value: str,
        event_id: str,
    ) -> bool:
        signature = row["source_signature"] or ""
        input_text = ""
        frag = None
        if not signature:
            fields = repo.get_fields(self.con, row["id"])
            values = {name: fields[name]["value"] for name in fields}
            values[field] = ""
            signature = field_signature_from_values(values, exclude=field)
        _, created = repo.upsert_example(
            self.con,
            target="field",
            field_name=field,
            input_signature=signature,
            input_text=input_text,
            label=sanitize_lims_value(new_value),
            source_kind="revision",
            source_event_id=event_id,
            session_id=session_id,
            bez1_context=row["bez1_context"] or "",
        )
        self._field_indexes.pop(field, None)
        return created

    def on_row_deleted(self, *, session_id: str, row: sqlite3.Row, event_id: str) -> bool:
        if (row["origin"] or "auto") != "auto":
            return False  # geloeschte manuelle Zeilen sind kein Erkennungssignal
        signature = row["source_signature"] or ""
        if not signature:
            return False
        _, created = repo.upsert_example(
            self.con,
            target="row",
            field_name="",
            input_signature=signature,
            input_text="",
            label="0",
            source_kind="row_delete",
            source_event_id=event_id,
            session_id=session_id,
            bez1_context=row["bez1_context"] or "",
        )
        self._row_clf = None
        return created

    def on_confirm_cell(
        self,
        *,
        session_id: str,
        row: sqlite3.Row,
        field: str,
        value: str,
        event_id: str,
    ) -> bool:
        created_any = False
        signature = row["source_signature"] or ""
        if not signature:
            fields = repo.get_fields(self.con, row["id"])
            values = {name: fields[name]["value"] for name in fields}
            signature = field_signature_from_values(values, exclude=field)
        if signature:
            _, created = repo.upsert_example(
                self.con,
                target="field",
                field_name=field,
                input_signature=signature,
                input_text="",
                label=sanitize_lims_value(value),
                source_kind="confirm",
                source_event_id=event_id,
                session_id=session_id,
                bez1_context=row["bez1_context"] or "",
            )
            created_any = created
            self._field_indexes.pop(field, None)
        # Bestaetigte manuell angelegte Zeile => positives Zeilenbeispiel
        if (row["origin"] or "auto") == "manual":
            sig = row["source_signature"] or ""
            if not sig:
                fields = repo.get_fields(self.con, row["id"])
                values = {name: fields[name]["value"] for name in fields}
                sig = field_signature_from_values(values, exclude="")
            if sig:
                _, created = repo.upsert_example(
                    self.con,
                    target="row",
                    field_name="",
                    input_signature=sig,
                    input_text="",
                    label="1",
                    source_kind="row_confirm",
                    source_event_id=event_id,
                    session_id=session_id,
                    bez1_context=row["bez1_context"] or "",
                )
                created_any = created_any or created
                self._row_clf = None
        return created_any

    def compensate_event(self, event_id: str) -> int:
        """Undo: alle aus dem Ereignis entstandenen Beispiele deaktivieren."""
        n = repo.deactivate_examples_for_event(self.con, event_id)
        if n:
            self.invalidate()
        return n

    # ------------------------------------------------------------ Rebuild

    def rebuild(self) -> dict:
        self.invalidate()
        counts = repo.example_counts(self.con)
        field_hashes = {}
        for field in FIELDS:
            field_hashes[field] = self._index_for(field).content_hash()
        clf = self.row_classifier()
        combined = json.dumps(field_hashes, sort_keys=True)
        from lims_assistant.textutil import sha256_text

        return {
            "examples_active": counts["field_active"],
            "examples_inactive": counts["field_inactive"],
            "row_examples_active": counts["row_active"],
            "index_hash": sha256_text(combined),
            "row_model_hash": clf.content_hash(),
        }

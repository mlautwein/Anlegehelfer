"""Job-Dispatcher: fuehrt einen validierten JobRequest gegen den Kern aus."""

from __future__ import annotations

import json
import platform
import sqlite3
import sys
from pathlib import Path

from lims_assistant import net_guard, paths
from lims_assistant.config import Settings
from lims_assistant.contracts.models import (
    AnalyzePayload,
    AppClosePayload,
    AppCloseResult,
    AppOpenPayload,
    AppOpenResult,
    ApplyRevisionPayload,
    ApplyRevisionResult,
    ConfirmCellsPayload,
    ConfirmCellsResult,
    ContractModel,
    ErrorInfo,
    ExportCsvPayload,
    ExportCsvResult,
    HealthResult,
    JobRequest,
    JobResponse,
    LearningHealth,
    ListSheetsPayload,
    ListSheetsResult,
    LlmHealth,
    LockState,
    OcrHealth,
    RebuildLearningResult,
    RowEventPayload,
    RowEventResult,
    UndoResult,
    make_response,
)
from lims_assistant.domain.entities import FIELDS
from lims_assistant.export.csv_export import export_five
from lims_assistant.learn.service import LearningService, field_signature_from_values
from lims_assistant.pipeline.analyze import AnalyzeCancelled, run_analyze
from lims_assistant.store import db, repo
from lims_assistant.sync.lock import LockBusyError, SharedLock
from lims_assistant.sync.snapshot import SnapshotError, SnapshotSync
from lims_assistant.version import APP_VERSION, DB_SCHEMA_VERSION, SCHEMA_VERSION

LOCK_SESSION_FILE = "lock-session.json"


def open_db(settings: Settings) -> sqlite3.Connection:
    paths.ensure_dirs()
    return db.connect(paths.local_db_path())


def _lock_session_path() -> Path:
    return paths.work_dir() / LOCK_SESSION_FILE


def _load_lock(settings: Settings) -> SharedLock | None:
    try:
        data = json.loads(_lock_session_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    lock = SharedLock(
        data["share_dir"],
        workstation=data.get("workstation", ""),
        stale_minutes=settings.stale_lock_minutes,
    )
    lock.nonce = data.get("nonce")
    return lock


def _save_lock(lock: SharedLock, share_dir: str) -> None:
    _lock_session_path().write_text(
        json.dumps(
            {
                "share_dir": share_dir,
                "nonce": lock.nonce,
                "workstation": lock.workstation,
            }
        ),
        encoding="utf-8",
    )


def _clear_lock_session() -> None:
    _lock_session_path().unlink(missing_ok=True)


def _lock_state(lock: SharedLock | None) -> LockState | None:
    if lock is None:
        return None
    return LockState(**lock.state_info())


# ---------------------------------------------------------------- Handler

def _handle_list_sheets(payload: ListSheetsPayload, settings: Settings, **_) -> ListSheetsResult:
    from lims_assistant.ingest.excel_ingest import list_sheets

    path = Path(payload.source_path)
    if not path.is_file():
        raise FileNotFoundError(f"Datei nicht gefunden: {path}")
    sheets, macros, warnings = list_sheets(path)
    return ListSheetsResult(sheets=sheets, has_macros=macros, warnings=warnings)


def _handle_analyze(
    payload: AnalyzePayload,
    settings: Settings,
    *,
    con: sqlite3.Connection,
    progress,
    cancelled,
    llm_adapter=None,
    **_,
):
    if llm_adapter is None and settings.llm.enabled:
        from lims_assistant.llm.llama_server import LlamaServerAdapter

        llm_adapter = LlamaServerAdapter(settings.llm)
    try:
        return run_analyze(
            con,
            settings,
            payload,
            llm_adapter=llm_adapter,
            progress=progress,
            cancelled=cancelled,
        )
    finally:
        if llm_adapter is not None:
            try:
                llm_adapter.close()
            except Exception:  # noqa: BLE001
                pass


def _handle_apply_revision(
    payload: ApplyRevisionPayload,
    settings: Settings,
    *,
    con: sqlite3.Connection,
    **_,
) -> ApplyRevisionResult:
    row = repo.get_row(con, payload.row_id)
    if row is None:
        raise ValueError(f"Unbekannte Zeile: {payload.row_id}")
    learning = LearningService(con)
    with con:
        event_id, created = repo.add_revision_event(
            con,
            session_id=payload.session_id,
            row_id=payload.row_id,
            field_name=payload.field,
            old_value=payload.old_value,
            new_value=payload.new_value,
            client_event_id=payload.client_event_id,
        )
        learned = False
        if created:
            repo.set_field(
                con,
                payload.row_id,
                payload.field,
                value=payload.new_value,
                is_uncertain=False,
                provenance="user",
            )
            learning.on_revision(
                session_id=payload.session_id,
                row=row,
                field=payload.field,
                new_value=payload.new_value,
                event_id=event_id,
            )
            learned = True
    return ApplyRevisionResult(event_id=event_id, learned=learned)


def _handle_row_event(
    payload: RowEventPayload,
    settings: Settings,
    *,
    con: sqlite3.Connection,
    **_,
) -> RowEventResult:
    learning = LearningService(con)
    with con:
        if payload.action == "add":
            values = payload.values or None
            values_map = values.model_dump() if values else {f: "" for f in FIELDS}
            existing = repo.get_row(con, payload.row_id)
            if existing is None:
                source_order = (
                    payload.source_order
                    if payload.source_order is not None
                    else repo.next_source_order(con, payload.session_id)
                )
                signature = field_signature_from_values(values_map, exclude="")
                repo.add_row(
                    con,
                    payload.session_id,
                    row_id=payload.row_id,
                    source_order=source_order,
                    origin="manual",
                    source_signature=signature,
                )
                for fname in FIELDS:
                    repo.set_field(
                        con,
                        payload.row_id,
                        fname,
                        value=values_map.get(fname, ""),
                        is_uncertain=False,
                        provenance="user",
                    )
            event_id, _created = repo.add_row_event(
                con,
                session_id=payload.session_id,
                row_id=payload.row_id,
                action="add",
                values_json=json.dumps(values_map, ensure_ascii=False),
                row_origin="manual",
                client_event_id=payload.client_event_id,
            )
        else:  # delete
            row = repo.get_row(con, payload.row_id)
            if row is None:
                raise ValueError(f"Unbekannte Zeile: {payload.row_id}")
            fields = repo.get_fields(con, payload.row_id)
            values_map = {name: fields[name]["value"] for name in fields}
            event_id, created = repo.add_row_event(
                con,
                session_id=payload.session_id,
                row_id=payload.row_id,
                action="delete",
                values_json=json.dumps(values_map, ensure_ascii=False),
                row_origin=row["origin"] or "auto",
                client_event_id=payload.client_event_id,
            )
            if created:
                repo.set_row_deleted(con, payload.row_id, True)
                learning.on_row_deleted(
                    session_id=payload.session_id, row=row, event_id=event_id
                )
    return RowEventResult(event_id=event_id)


def _handle_confirm_cells(
    payload: ConfirmCellsPayload,
    settings: Settings,
    *,
    con: sqlite3.Connection,
    **_,
) -> ConfirmCellsResult:
    learning = LearningService(con)
    confirmed = 0
    new_examples = 0
    duplicates = 0
    with con:
        for cell in payload.cells:
            row = repo.get_row(con, cell.row_id)
            if row is None:
                continue
            event_id, created = repo.add_confirmation(
                con,
                session_id=payload.session_id,
                confirmation_type=payload.confirmation_type,
                row_id=cell.row_id,
                field_name=cell.field,
                value=cell.value,
                client_event_id=payload.client_event_id,
            )
            confirmed += 1
            if created and event_id:
                if learning.on_confirm_cell(
                    session_id=payload.session_id,
                    row=row,
                    field=cell.field,
                    value=cell.value,
                    event_id=event_id,
                ):
                    new_examples += 1
            else:
                duplicates += 1
    return ConfirmCellsResult(
        confirmed=confirmed, new_examples=new_examples, duplicates=duplicates
    )


def _handle_undo(payload, settings: Settings, *, con: sqlite3.Connection, **_) -> UndoResult:
    learning = LearningService(con)
    with con:
        last = repo.last_undoable_event(con, payload.session_id)
        if last is None:
            return UndoResult()
        kind = last["kind"]
        event_id = last["event_id"]
        if kind == "revision":
            ev = con.execute(
                "SELECT * FROM revision_event WHERE id=?", (event_id,)
            ).fetchone()
            repo.deactivate_event(con, "revision", event_id)
            repo.set_field(
                con,
                ev["row_id"],
                ev["field_name"],
                value=ev["old_value"],
                is_uncertain=False,
                provenance="undo",
            )
            learning.compensate_event(event_id)
            return UndoResult(compensated_event_id=event_id, compensated_kind="revision")
        ev = con.execute("SELECT * FROM row_event WHERE id=?", (event_id,)).fetchone()
        repo.deactivate_event(con, "row", event_id)
        if ev["action"] == "add":
            repo.set_row_deleted(con, ev["row_id"], True)
        else:
            repo.set_row_deleted(con, ev["row_id"], False)
        learning.compensate_event(event_id)
        return UndoResult(
            compensated_event_id=event_id, compensated_kind=f"row_{ev['action']}"
        )


def _handle_rebuild(payload, settings: Settings, *, con: sqlite3.Connection, **_) -> RebuildLearningResult:
    learning = LearningService(con)
    with con:
        stats = learning.rebuild()
    return RebuildLearningResult(**stats)


def _handle_export(payload: ExportCsvPayload, settings: Settings, *, con: sqlite3.Connection, **_) -> ExportCsvResult:
    target_dir = payload.target_dir
    if not target_dir and payload.session_id:
        session = repo.get_session(con, payload.session_id)
        if session is not None:
            target_dir = session["export_base_dir"] or None
    if not target_dir:
        raise ValueError(
            "Kein Exportziel: weder target_dir angegeben noch Session mit Quellordner"
        )
    matrix = [r.values.as_list() for r in payload.rows]
    files, hashes = export_five(matrix, target_dir, encoding=payload.encoding)
    learning = LearningService(con)
    with con:
        repo.add_export_event(
            con,
            session_id=payload.session_id or "",
            encoding=payload.encoding,
            row_count=len(matrix),
            target_dir=str(target_dir),
            files=files,
            hashes=hashes,
        )
        if payload.session_id:
            for row in payload.rows:
                if not row.row_id:
                    continue
                db_row = repo.get_row(con, row.row_id)
                if db_row is None:
                    continue
                values = row.values.model_dump()
                for fname in FIELDS:
                    event_id, created = repo.add_confirmation(
                        con,
                        session_id=payload.session_id,
                        confirmation_type="export",
                        row_id=row.row_id,
                        field_name=fname,
                        value=values.get(fname, ""),
                        client_event_id=payload.client_event_id or "export",
                    )
                    if created and event_id:
                        learning.on_confirm_cell(
                            session_id=payload.session_id,
                            row=db_row,
                            field=fname,
                            value=values.get(fname, ""),
                            event_id=event_id,
                        )
    return ExportCsvResult(
        files=files,
        row_count=len(matrix),
        encoding=payload.encoding,
        target_dir=str(target_dir),
    )


def _handle_app_open(payload: AppOpenPayload, settings: Settings, *, con: sqlite3.Connection, **_) -> AppOpenResult:
    share = payload.share_dir or settings.share_dir
    warnings: list[str] = []
    if not share:
        return AppOpenResult(
            lock_acquired=True,
            read_only=False,
            warnings=["Kein gemeinsamer Ordner konfiguriert - rein lokaler Betrieb."],
        )
    lock = SharedLock(
        share,
        workstation=payload.workstation,
        stale_minutes=settings.stale_lock_minutes,
    )
    try:
        lock.acquire(takeover_stale=payload.takeover_stale)
    except LockBusyError as exc:
        state = _lock_state(lock)
        warnings.append(str(exc))
        if exc.stale:
            warnings.append(
                "Der Lock ist veraltet. Uebernahme ist nur nach Benutzerbestaetigung "
                "moeglich (takeover_stale)."
            )
        return AppOpenResult(
            lock_acquired=False, read_only=True, lock=state, warnings=warnings
        )
    _save_lock(lock, share)

    sync = SnapshotSync(share, paths.local_db_path())
    pulled = False
    pending_pushed = False
    try:
        if sync.has_pending():
            con.close()
            sync.push()
            pending_pushed = True
            warnings.append("Ausstehender lokaler Stand wurde synchronisiert.")
        else:
            con.close()
            pulled = sync.pull()
    except SnapshotError as exc:
        warnings.append(str(exc))
    return AppOpenResult(
        lock_acquired=True,
        read_only=False,
        lock=_lock_state(lock),
        snapshot_pulled=pulled,
        pending_pushed=pending_pushed,
        warnings=warnings,
    )


def _handle_app_close(payload: AppClosePayload, settings: Settings, *, con: sqlite3.Connection, **_) -> AppCloseResult:
    warnings: list[str] = []
    lock = _load_lock(settings)
    pushed = False
    pending = False
    if lock is not None:
        share_dir = str(lock.lock_dir.parent)
        sync = SnapshotSync(share_dir, paths.local_db_path())
        try:
            con.close()
            pushed = sync.push()
        except SnapshotError as exc:
            pending = True
            warnings.append(str(exc))
        released = False
        if payload.release_lock:
            released = lock.release()
            _clear_lock_session()
        removed = paths.sweep_stale()
        if removed:
            warnings.append(f"{removed} verwaiste Temporaereintraege bereinigt.")
        return AppCloseResult(
            snapshot_pushed=pushed,
            pending=pending,
            lock_released=released,
            warnings=warnings,
        )
    removed = paths.sweep_stale()
    if removed:
        warnings.append(f"{removed} verwaiste Temporaereintraege bereinigt.")
    return AppCloseResult(
        snapshot_pushed=False, pending=False, lock_released=False, warnings=warnings
    )


def _handle_health(payload, settings: Settings, *, con: sqlite3.Connection, **_) -> HealthResult:
    from lims_assistant.ocr.base import engine_health

    engine, available, detail = engine_health(settings.ocr)
    counts = repo.example_counts(con)
    llm_model = Path(settings.llm.model_path) if settings.llm.model_path else None
    llm_bin = Path(settings.llm.server_binary) if settings.llm.server_binary else None
    sha_ok = None
    if llm_model and llm_model.is_file() and settings.llm.model_sha256:
        from lims_assistant.textutil import sha256_file

        sha_ok = sha256_file(llm_model) == settings.llm.model_sha256.lower()
    lock = _load_lock(settings)
    return HealthResult(
        app_version=APP_VERSION,
        schema_version=SCHEMA_VERSION,
        db_schema_version=db.get_schema_version(con),
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        data_dir=str(paths.data_root()),
        db_path=str(paths.local_db_path()),
        ocr=OcrHealth(engine=engine, available=available, detail=detail),
        llm=LlmHealth(
            enabled=settings.llm.enabled,
            model_path=settings.llm.model_path,
            model_present=bool(llm_model and llm_model.is_file()),
            model_sha256_ok=sha_ok,
            server_binary_present=bool(llm_bin and llm_bin.is_file()),
        ),
        learning=LearningHealth(
            examples_active=counts["field_active"],
            row_examples_active=counts["row_active"],
            sessions=repo.count_sessions(con),
        ),
        lock=_lock_state(lock),
        offline_guard=net_guard.is_installed(),
    )


_HANDLERS = {
    "list_sheets": _handle_list_sheets,
    "analyze": _handle_analyze,
    "apply_revision": _handle_apply_revision,
    "row_event": _handle_row_event,
    "confirm_cells": _handle_confirm_cells,
    "undo": _handle_undo,
    "rebuild_learning": _handle_rebuild,
    "export_csv": _handle_export,
    "app_open": _handle_app_open,
    "app_close": _handle_app_close,
    "health": _handle_health,
}


def execute(
    request: JobRequest,
    settings: Settings,
    *,
    progress=lambda phase, percent, message: None,
    cancelled=lambda: False,
    llm_adapter=None,
) -> JobResponse:
    handler = _HANDLERS[request.kind]
    con = open_db(settings)
    try:
        payload = request.typed_payload()
        result: ContractModel = handler(
            payload,
            settings,
            con=con,
            progress=progress,
            cancelled=cancelled,
            llm_adapter=llm_adapter,
        )
        return make_response(request, result=result)
    except AnalyzeCancelled:
        return make_response(
            request,
            error=ErrorInfo(code="cancelled", message="Analyse abgebrochen."),
        )
    except FileNotFoundError as exc:
        return make_response(
            request, error=ErrorInfo(code="not_found", message=str(exc))
        )
    except (ValueError, KeyError) as exc:
        return make_response(
            request, error=ErrorInfo(code="bad_request", message=str(exc))
        )
    except SnapshotError as exc:
        return make_response(
            request, error=ErrorInfo(code="sync_error", message=str(exc))
        )
    except Exception as exc:  # noqa: BLE001 - kontrollierte Fehlerantwort
        return make_response(
            request,
            error=ErrorInfo(
                code="internal",
                message="Interner Fehler im Rechenkern.",
                detail=f"{type(exc).__name__}: {exc}",
            ),
        )
    finally:
        try:
            con.close()
        except sqlite3.ProgrammingError:
            pass  # Handler (app_open/close) duerfen con selbst schliessen

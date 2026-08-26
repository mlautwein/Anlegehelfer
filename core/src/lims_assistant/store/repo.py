"""Datenzugriffsschicht ueber der lokalen SQLite-Datenbank."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from lims_assistant.domain.entities import FIELDS
from lims_assistant.textutil import sha256_text


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_id() -> str:
    import uuid

    return str(uuid.uuid4())


# ---------------------------------------------------------------- Sessions

def create_session(con: sqlite3.Connection, hint_text: str = "") -> str:
    sid = new_id()
    con.execute(
        "INSERT INTO import_session(id, created_utc, hint_text) VALUES(?,?,?)",
        (sid, now_iso(), hint_text),
    )
    return sid


def get_session(con: sqlite3.Connection, session_id: str) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM import_session WHERE id=?", (session_id,)
    ).fetchone()


def set_session_export_dir(con: sqlite3.Connection, session_id: str, base_dir: str) -> None:
    con.execute(
        "UPDATE import_session SET export_base_dir=? WHERE id=? AND export_base_dir=''",
        (base_dir, session_id),
    )


def append_session_hint(con: sqlite3.Connection, session_id: str, hint_text: str) -> None:
    if not hint_text:
        return
    row = get_session(con, session_id)
    existing = row["hint_text"] if row else ""
    merged = (existing + "\n" + hint_text).strip() if existing else hint_text
    con.execute("UPDATE import_session SET hint_text=? WHERE id=?", (merged, session_id))


def count_sessions(con: sqlite3.Connection) -> int:
    return int(con.execute("SELECT COUNT(*) FROM import_session").fetchone()[0])


# ---------------------------------------------------------------- Dokumente

def add_document(
    con: sqlite3.Connection,
    session_id: str,
    *,
    doc_type: str,
    filename: str,
    sha256: str,
    extracted_text: str,
    hint_text: str = "",
    page_selection: str = "",
    sheet_selection: str = "",
) -> str:
    did = new_id()
    order = int(
        con.execute(
            "SELECT COALESCE(MAX(doc_order), -1) + 1 FROM source_document WHERE session_id=?",
            (session_id,),
        ).fetchone()[0]
    )
    con.execute(
        "INSERT INTO source_document(id, session_id, type, filename, sha256, extracted_text,"
        " hint_text, page_selection, sheet_selection, doc_order, created_utc)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            did,
            session_id,
            doc_type,
            filename,
            sha256,
            extracted_text,
            hint_text,
            page_selection,
            sheet_selection,
            order,
            now_iso(),
        ),
    )
    return did


def add_fragment(
    con: sqlite3.Connection,
    document_id: str,
    *,
    page_or_sheet: str,
    frag_order: int,
    text: str,
    kind: str = "line",
    bbox: str = "",
    ocr_score: float | None = None,
) -> str:
    fid = new_id()
    con.execute(
        "INSERT INTO source_fragment(id, document_id, page_or_sheet, frag_order, kind, text,"
        " bbox, ocr_score) VALUES(?,?,?,?,?,?,?,?)",
        (fid, document_id, page_or_sheet, frag_order, kind, text, bbox, ocr_score),
    )
    return fid


# ---------------------------------------------------------------- Zeilen/Felder

def next_source_order(con: sqlite3.Connection, session_id: str) -> int:
    return int(
        con.execute(
            "SELECT COALESCE(MAX(source_order), 0) + 1 FROM sample_row WHERE session_id=?",
            (session_id,),
        ).fetchone()[0]
    )


def add_row(
    con: sqlite3.Connection,
    session_id: str,
    *,
    row_id: str | None = None,
    source_order: int,
    origin: str = "auto",
    fragment_id: str | None = None,
    source_signature: str = "",
    bez1_context: str = "",
) -> str:
    rid = row_id or new_id()
    con.execute(
        "INSERT INTO sample_row(id, session_id, source_order, current_order, origin,"
        " fragment_id, source_signature, bez1_context, created_utc)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (
            rid,
            session_id,
            source_order,
            source_order,
            origin,
            fragment_id,
            source_signature,
            bez1_context,
            now_iso(),
        ),
    )
    for name in FIELDS:
        con.execute(
            "INSERT INTO sample_field(id, row_id, field_name) VALUES(?,?,?)",
            (new_id(), rid, name),
        )
    return rid


def get_row(con: sqlite3.Connection, row_id: str) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM sample_row WHERE id=?", (row_id,)).fetchone()


def set_row_deleted(con: sqlite3.Connection, row_id: str, deleted: bool) -> None:
    con.execute(
        "UPDATE sample_row SET deleted=? WHERE id=?", (1 if deleted else 0, row_id)
    )


def set_field(
    con: sqlite3.Connection,
    row_id: str,
    field_name: str,
    *,
    value: str,
    is_uncertain: bool,
    provenance: str,
) -> str:
    con.execute(
        "UPDATE sample_field SET value=?, is_uncertain=?, provenance=?"
        " WHERE row_id=? AND field_name=?",
        (value, 1 if is_uncertain else 0, provenance, row_id, field_name),
    )
    row = con.execute(
        "SELECT id FROM sample_field WHERE row_id=? AND field_name=?",
        (row_id, field_name),
    ).fetchone()
    return row["id"]


def get_fields(con: sqlite3.Connection, row_id: str) -> dict[str, sqlite3.Row]:
    rows = con.execute(
        "SELECT * FROM sample_field WHERE row_id=?", (row_id,)
    ).fetchall()
    return {r["field_name"]: r for r in rows}


def add_proposal(
    con: sqlite3.Connection,
    field_id: str,
    *,
    value: str,
    provenance: str,
    score: float,
    component_scores: dict,
    model_version: str,
    normalizer_version: str,
    is_uncertain: bool,
) -> str:
    pid = new_id()
    con.execute(
        "INSERT INTO field_proposal(id, field_id, value, provenance, score,"
        " component_scores, model_version, normalizer_version, is_uncertain, created_utc)"
        " VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            pid,
            field_id,
            value,
            provenance,
            round(float(score), 4),
            json.dumps(component_scores, ensure_ascii=False, sort_keys=True),
            model_version,
            normalizer_version,
            1 if is_uncertain else 0,
            now_iso(),
        ),
    )
    return pid


# ---------------------------------------------------------------- Ereignisse

def _log_event(con: sqlite3.Connection, kind: str, event_id: str, session_id: str) -> None:
    con.execute(
        "INSERT INTO event_log(kind, event_id, session_id, created_utc) VALUES(?,?,?,?)",
        (kind, event_id, session_id, now_iso()),
    )


def add_revision_event(
    con: sqlite3.Connection,
    *,
    session_id: str,
    row_id: str,
    field_name: str,
    old_value: str,
    new_value: str,
    client_event_id: str,
) -> tuple[str, bool]:
    """Rueckgabe: (event_id, neu_angelegt). Idempotent je client_event_id."""
    existing = con.execute(
        "SELECT id FROM revision_event WHERE client_event_id=?", (client_event_id,)
    ).fetchone()
    if existing:
        return existing["id"], False
    eid = new_id()
    con.execute(
        "INSERT INTO revision_event(id, session_id, row_id, field_name, old_value,"
        " new_value, client_event_id, created_utc) VALUES(?,?,?,?,?,?,?,?)",
        (eid, session_id, row_id, field_name, old_value, new_value, client_event_id, now_iso()),
    )
    _log_event(con, "revision", eid, session_id)
    return eid, True


def add_row_event(
    con: sqlite3.Connection,
    *,
    session_id: str,
    row_id: str,
    action: str,
    values_json: str,
    row_origin: str,
    client_event_id: str,
) -> tuple[str, bool]:
    existing = con.execute(
        "SELECT id FROM row_event WHERE client_event_id=?", (client_event_id,)
    ).fetchone()
    if existing:
        return existing["id"], False
    eid = new_id()
    con.execute(
        "INSERT INTO row_event(id, session_id, row_id, action, values_json, row_origin,"
        " client_event_id, created_utc) VALUES(?,?,?,?,?,?,?,?)",
        (eid, session_id, row_id, action, values_json, row_origin, client_event_id, now_iso()),
    )
    _log_event(con, f"row_{action}", eid, session_id)
    return eid, True


def confirmation_dedupe_key(row_id: str, field_name: str, value: str) -> str:
    return sha256_text(f"confirm|{row_id}|{field_name}|{value}")


def add_confirmation(
    con: sqlite3.Connection,
    *,
    session_id: str,
    confirmation_type: str,
    row_id: str,
    field_name: str,
    value: str,
    client_event_id: str,
) -> tuple[str | None, bool]:
    """Idempotent: gleiche Zelle + gleicher Wert => kein Mehrfachgewicht."""
    key = confirmation_dedupe_key(row_id, field_name, value)
    existing = con.execute(
        "SELECT id FROM confirmation_event WHERE dedupe_key=?", (key,)
    ).fetchone()
    if existing:
        return existing["id"], False
    eid = new_id()
    con.execute(
        "INSERT INTO confirmation_event(id, session_id, confirmation_type, dedupe_key,"
        " row_id, field_name, value, client_event_id, created_utc)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (eid, session_id, confirmation_type, key, row_id, field_name, value, client_event_id, now_iso()),
    )
    return eid, True


def last_undoable_event(con: sqlite3.Connection, session_id: str) -> sqlite3.Row | None:
    """Letztes aktives Revision-/Row-Ereignis der Session (fuer Ein-Schritt-Undo)."""
    return con.execute(
        """
        SELECT el.seq, el.kind, el.event_id FROM event_log el
        WHERE el.session_id = ?
          AND (
            (el.kind = 'revision' AND EXISTS (
                SELECT 1 FROM revision_event re WHERE re.id = el.event_id AND re.active = 1))
            OR
            (el.kind IN ('row_add', 'row_delete') AND EXISTS (
                SELECT 1 FROM row_event rw WHERE rw.id = el.event_id AND rw.active = 1))
          )
        ORDER BY el.seq DESC LIMIT 1
        """,
        (session_id,),
    ).fetchone()


def deactivate_event(con: sqlite3.Connection, kind: str, event_id: str) -> None:
    table = "revision_event" if kind == "revision" else "row_event"
    con.execute(f"UPDATE {table} SET active=0 WHERE id=?", (event_id,))


# ---------------------------------------------------------------- Lernbeispiele

def example_dedupe_key(target: str, field_name: str, input_signature: str, label: str) -> str:
    return sha256_text(f"ex|{target}|{field_name}|{input_signature}|{label}")


def upsert_example(
    con: sqlite3.Connection,
    *,
    target: str,
    field_name: str,
    input_signature: str,
    input_text: str,
    label: str,
    source_kind: str,
    source_event_id: str,
    session_id: str,
    bez1_context: str = "",
) -> tuple[str, bool]:
    """Legt ein Lernbeispiel an oder reaktiviert es. Idempotent, Gewicht bleibt 1."""
    key = example_dedupe_key(target, field_name, input_signature, label)
    existing = con.execute(
        "SELECT id, active FROM learning_example WHERE dedupe_key=?", (key,)
    ).fetchone()
    ts = now_iso()
    if existing:
        con.execute(
            "UPDATE learning_example SET active=1, updated_utc=? WHERE id=?",
            (ts, existing["id"]),
        )
        return existing["id"], False
    eid = new_id()
    con.execute(
        "INSERT INTO learning_example(id, target, field_name, input_signature, input_text,"
        " label, dedupe_key, source_kind, source_event_id, session_id, bez1_context,"
        " created_utc, updated_utc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            eid,
            target,
            field_name,
            input_signature,
            input_text,
            label,
            key,
            source_kind,
            source_event_id,
            session_id,
            bez1_context,
            ts,
            ts,
        ),
    )
    return eid, True


def deactivate_examples_for_event(con: sqlite3.Connection, source_event_id: str) -> int:
    cur = con.execute(
        "UPDATE learning_example SET active=0, updated_utc=? WHERE source_event_id=?",
        (now_iso(), source_event_id),
    )
    return cur.rowcount


def active_examples(
    con: sqlite3.Connection, target: str, field_name: str | None = None
) -> list[sqlite3.Row]:
    if field_name is None:
        return con.execute(
            "SELECT * FROM learning_example WHERE target=? AND active=1"
            " ORDER BY created_utc, id",
            (target,),
        ).fetchall()
    return con.execute(
        "SELECT * FROM learning_example WHERE target=? AND field_name=? AND active=1"
        " ORDER BY created_utc, id",
        (target, field_name),
    ).fetchall()


def example_counts(con: sqlite3.Connection) -> dict[str, int]:
    def q(sql: str) -> int:
        return int(con.execute(sql).fetchone()[0])

    return {
        "field_active": q(
            "SELECT COUNT(*) FROM learning_example WHERE target='field' AND active=1"
        ),
        "field_inactive": q(
            "SELECT COUNT(*) FROM learning_example WHERE target='field' AND active=0"
        ),
        "row_active": q(
            "SELECT COUNT(*) FROM learning_example WHERE target='row' AND active=1"
        ),
    }


# ---------------------------------------------------------------- Export/Snapshots

def add_export_event(
    con: sqlite3.Connection,
    *,
    session_id: str,
    encoding: str,
    row_count: int,
    target_dir: str,
    files: list[str],
    hashes: dict[str, str],
) -> str:
    eid = new_id()
    con.execute(
        "INSERT INTO export_event(id, session_id, encoding, row_count, target_dir,"
        " files_json, hashes_json, created_utc) VALUES(?,?,?,?,?,?,?,?)",
        (
            eid,
            session_id,
            encoding,
            row_count,
            target_dir,
            json.dumps(files, ensure_ascii=False),
            json.dumps(hashes, ensure_ascii=False, sort_keys=True),
            now_iso(),
        ),
    )
    return eid


def add_snapshot_event(
    con: sqlite3.Connection, *, schema_version: int, db_sha256: str, direction: str
) -> str:
    sid = new_id()
    con.execute(
        "INSERT INTO data_snapshot(id, schema_version, db_sha256, direction, created_utc)"
        " VALUES(?,?,?,?,?)",
        (sid, schema_version, db_sha256, direction, now_iso()),
    )
    return sid

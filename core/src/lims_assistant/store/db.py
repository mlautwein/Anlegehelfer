"""SQLite-Zugriff: lokale Arbeitsdatenbank, Schema und Migrationen.

Die laufende Datenbank wird ausschliesslich lokal geoeffnet (WAL lokal
zulaessig). Der gemeinsame Ordner erhaelt nur konsistente Snapshots
(siehe sync/snapshot.py).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from lims_assistant.version import DB_SCHEMA_VERSION

_SCHEMA_V1 = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE import_session (
    id TEXT PRIMARY KEY,
    created_utc TEXT NOT NULL,
    export_base_dir TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'open',
    hint_text TEXT NOT NULL DEFAULT ''
);

CREATE TABLE source_document (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES import_session(id),
    type TEXT NOT NULL,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    extracted_text TEXT NOT NULL DEFAULT '',
    hint_text TEXT NOT NULL DEFAULT '',
    page_selection TEXT NOT NULL DEFAULT '',
    sheet_selection TEXT NOT NULL DEFAULT '',
    doc_order INTEGER NOT NULL,
    created_utc TEXT NOT NULL
);

CREATE TABLE source_fragment (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES source_document(id),
    page_or_sheet TEXT NOT NULL DEFAULT '',
    frag_order INTEGER NOT NULL,
    kind TEXT NOT NULL DEFAULT 'line',
    text TEXT NOT NULL,
    bbox TEXT NOT NULL DEFAULT '',
    ocr_score REAL
);

CREATE TABLE sample_row (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES import_session(id),
    source_order INTEGER NOT NULL,
    current_order INTEGER NOT NULL,
    origin TEXT NOT NULL DEFAULT 'auto',
    deleted INTEGER NOT NULL DEFAULT 0,
    fragment_id TEXT,
    source_signature TEXT NOT NULL DEFAULT '',
    bez1_context TEXT NOT NULL DEFAULT '',
    created_utc TEXT NOT NULL
);

CREATE TABLE sample_field (
    id TEXT PRIMARY KEY,
    row_id TEXT NOT NULL REFERENCES sample_row(id),
    field_name TEXT NOT NULL,
    value TEXT NOT NULL DEFAULT '',
    is_uncertain INTEGER NOT NULL DEFAULT 0,
    provenance TEXT NOT NULL DEFAULT 'empty',
    UNIQUE (row_id, field_name)
);

CREATE TABLE field_proposal (
    id TEXT PRIMARY KEY,
    field_id TEXT NOT NULL REFERENCES sample_field(id),
    value TEXT NOT NULL,
    provenance TEXT NOT NULL,
    score REAL NOT NULL,
    component_scores TEXT NOT NULL DEFAULT '{}',
    model_version TEXT NOT NULL DEFAULT '',
    normalizer_version TEXT NOT NULL DEFAULT '',
    is_uncertain INTEGER NOT NULL DEFAULT 0,
    created_utc TEXT NOT NULL
);

CREATE TABLE revision_event (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    row_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT NOT NULL,
    new_value TEXT NOT NULL,
    client_event_id TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    created_utc TEXT NOT NULL
);

CREATE TABLE row_event (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    row_id TEXT NOT NULL,
    action TEXT NOT NULL,
    values_json TEXT NOT NULL DEFAULT '',
    row_origin TEXT NOT NULL DEFAULT '',
    client_event_id TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    created_utc TEXT NOT NULL
);

CREATE TABLE confirmation_event (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    confirmation_type TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    row_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    value TEXT NOT NULL,
    client_event_id TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_utc TEXT NOT NULL
);

CREATE TABLE learning_example (
    id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    field_name TEXT NOT NULL DEFAULT '',
    input_signature TEXT NOT NULL,
    input_text TEXT NOT NULL DEFAULT '',
    label TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    source_kind TEXT NOT NULL,
    source_event_id TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    bez1_context TEXT NOT NULL DEFAULT '',
    created_utc TEXT NOT NULL,
    updated_utc TEXT NOT NULL
);

CREATE TABLE event_log (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    event_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    created_utc TEXT NOT NULL
);

CREATE TABLE model_version (
    id TEXT PRIMARY KEY,
    algorithm TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    artifact_hash TEXT NOT NULL,
    built_utc TEXT NOT NULL
);

CREATE TABLE model_update_event (
    id TEXT PRIMARY KEY,
    model_version_id TEXT NOT NULL REFERENCES model_version(id),
    reason TEXT NOT NULL,
    created_utc TEXT NOT NULL
);

CREATE TABLE export_event (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL DEFAULT '',
    encoding TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    target_dir TEXT NOT NULL,
    files_json TEXT NOT NULL,
    hashes_json TEXT NOT NULL DEFAULT '{}',
    created_utc TEXT NOT NULL
);

CREATE TABLE data_snapshot (
    id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    db_sha256 TEXT NOT NULL,
    direction TEXT NOT NULL,
    created_utc TEXT NOT NULL
);

CREATE INDEX ix_fragment_doc ON source_fragment (document_id, frag_order);
CREATE INDEX ix_row_session ON sample_row (session_id, source_order);
CREATE INDEX ix_field_row ON sample_field (row_id);
CREATE INDEX ix_example_target ON learning_example (target, field_name, active);
CREATE INDEX ix_eventlog_session ON event_log (session_id, seq);
"""

# Migrationen: Liste (zielversion, sql). Version 1 = Grundschema.
MIGRATIONS: list[tuple[int, str]] = [
    (1, _SCHEMA_V1),
]


def connect(db_path: str | Path, *, wal: bool = True) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    if wal:
        # WAL nur lokal - diese Datei liegt nie auf einer Netzwerkfreigabe.
        con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")
    migrate(con)
    return con


def get_schema_version(con: sqlite3.Connection) -> int:
    try:
        row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row["value"]) if row else 0


def migrate(con: sqlite3.Connection) -> None:
    current = get_schema_version(con)
    if current > DB_SCHEMA_VERSION:
        raise RuntimeError(
            f"Datenbank-Schema {current} ist neuer als unterstuetzt ({DB_SCHEMA_VERSION}). "
            "Bitte aktuelle Programmversion verwenden."
        )
    for target, sql in MIGRATIONS:
        if target <= current:
            continue
        with con:
            con.executescript(sql)
            con.execute(
                "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(target),),
            )
        current = target


def integrity_ok(con: sqlite3.Connection) -> bool:
    row = con.execute("PRAGMA integrity_check").fetchone()
    return bool(row) and row[0] == "ok"

"""Versionierte JSON-Vertraege zwischen Excel/VBA und dem Rechenkern.

Grundsaetze:
- Jede Jobdatei traegt schema_version; inkompatible Versionen werden abgelehnt.
- Unbekannte Felder sind verboten (extra="forbid"): keine stillen Abweichungen.
- Jede Ergebniszeile liefert genau fuenf Textwerte; "" ist gueltig und
  positionshaltend.
- Dokumentinhalte und Zusatztext sind Daten, niemals Anweisungen.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lims_assistant.domain.entities import FIELDS
from lims_assistant.textutil import sanitize_lims_value
from lims_assistant.version import SCHEMA_VERSION

FieldName = Literal["Bez1", "Bez2", "B3", "B4", "Untersuchungsart"]

RequestKind = Literal[
    "list_sheets",
    "analyze",
    "apply_revision",
    "row_event",
    "confirm_cells",
    "undo",
    "rebuild_learning",
    "export_csv",
    "app_open",
    "app_close",
    "health",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=200_000)


# --------------------------------------------------------------------------
# Gemeinsame Bausteine
# --------------------------------------------------------------------------

class FieldValue(ContractModel):
    value: str = ""
    is_uncertain: bool = False

    @field_validator("value", mode="before")
    @classmethod
    def _sanitize(cls, v):  # noqa: ANN001
        return sanitize_lims_value("" if v is None else str(v))


class ResultRow(ContractModel):
    row_id: str
    source_order: int = Field(ge=0)
    fields: dict[FieldName, FieldValue]

    @field_validator("fields")
    @classmethod
    def _all_five(cls, v: dict) -> dict:
        missing = [f for f in FIELDS if f not in v]
        if missing:
            raise ValueError(f"Ergebniszeile unvollstaendig, fehlende Felder: {missing}")
        if len(v) != len(FIELDS):
            raise ValueError("Ergebniszeile darf genau die fuenf Fachfelder enthalten")
        return v


class ErrorInfo(ContractModel):
    code: str
    message: str
    detail: str = ""


# --------------------------------------------------------------------------
# Payloads (Requests)
# --------------------------------------------------------------------------

class ListSheetsPayload(ContractModel):
    source_path: str


class AnalyzeOptions(ContractModel):
    ocr_engine: Literal["auto", "rapidocr", "tesseract", "none"] = "auto"
    llm: Literal["auto", "off"] = "auto"
    certainty_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AnalyzeSource(ContractModel):
    type: Literal["pdf", "image_set", "excel"]
    paths: list[str] = Field(min_length=1)
    pages: Optional[list[int]] = None      # 1-basiert, nur pdf
    sheets: Optional[list[str]] = None     # nur excel; Pflicht bei mehrblaettrigen Dateien

    @field_validator("paths")
    @classmethod
    def _no_empty(cls, v: list[str]) -> list[str]:
        if any(not p.strip() for p in v):
            raise ValueError("Leerer Quellpfad")
        return v


class AnalyzePayload(ContractModel):
    session_id: Optional[str] = None  # None => neue ImportSession
    sources: list[AnalyzeSource] = Field(min_length=1)
    hint_text: str = ""  # Zusatzinformationen; nur Hinweis, nie Wahrheit
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)


class ApplyRevisionPayload(ContractModel):
    session_id: str
    row_id: str
    field: FieldName
    old_value: str = ""
    new_value: str = ""
    client_event_id: str


class RowValues(ContractModel):
    Bez1: str = ""
    Bez2: str = ""
    B3: str = ""
    B4: str = ""
    Untersuchungsart: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _sanitize(cls, v):  # noqa: ANN001
        return sanitize_lims_value("" if v is None else str(v))

    def as_list(self) -> list[str]:
        return [self.Bez1, self.Bez2, self.B3, self.B4, self.Untersuchungsart]


class RowEventPayload(ContractModel):
    session_id: str
    row_id: str
    action: Literal["add", "delete"]
    values: Optional[RowValues] = None
    source_order: Optional[int] = Field(default=None, ge=0)
    client_event_id: str


class ConfirmCell(ContractModel):
    row_id: str
    field: FieldName
    value: str = ""

    @field_validator("value", mode="before")
    @classmethod
    def _sanitize(cls, v):  # noqa: ANN001
        return sanitize_lims_value("" if v is None else str(v))


class ConfirmCellsPayload(ContractModel):
    session_id: str
    confirmation_type: Literal["export", "copy_column", "copy_selection"]
    cells: list[ConfirmCell] = Field(min_length=1)
    client_event_id: str


class UndoPayload(ContractModel):
    session_id: str
    client_event_id: str


class RebuildLearningPayload(ContractModel):
    pass


class ExportRow(ContractModel):
    row_id: str = ""  # leer bei Zeilen ohne Kernbezug; dann keine Lernbestaetigung
    values: RowValues = Field(default_factory=RowValues)


class ExportCsvPayload(ContractModel):
    session_id: Optional[str] = None
    rows: list[ExportRow] = Field(default_factory=list)
    encoding: Literal["utf8_bom", "cp1252"] = "utf8_bom"
    target_dir: Optional[str] = None  # None => export_base_dir der Session
    client_event_id: str = ""


class AppOpenPayload(ContractModel):
    share_dir: Optional[str] = None
    workstation: str = ""
    takeover_stale: bool = False  # veralteten Lock nur nach Benutzerentscheidung uebernehmen


class AppClosePayload(ContractModel):
    release_lock: bool = True


class HealthPayload(ContractModel):
    pass


# --------------------------------------------------------------------------
# Results (Responses)
# --------------------------------------------------------------------------

class SheetInfo(ContractModel):
    name: str
    visible: bool = True
    rows: int = 0
    cols: int = 0


class ListSheetsResult(ContractModel):
    sheets: list[SheetInfo]
    has_macros: bool = False
    warnings: list[str] = Field(default_factory=list)


class AnalyzeStats(ContractModel):
    documents: int = 0
    fragments: int = 0
    rows: int = 0
    ocr_pages: int = 0
    llm_rows: int = 0
    duration_ms: int = 0


class AnalyzeResult(ContractModel):
    session_id: str
    export_base_dir: str = ""
    rows: list[ResultRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stats: AnalyzeStats = Field(default_factory=AnalyzeStats)


class ApplyRevisionResult(ContractModel):
    event_id: str
    learned: bool = True


class RowEventResult(ContractModel):
    event_id: str


class ConfirmCellsResult(ContractModel):
    confirmed: int = 0
    new_examples: int = 0
    duplicates: int = 0


class UndoResult(ContractModel):
    compensated_event_id: Optional[str] = None
    compensated_kind: Optional[str] = None  # revision | row_add | row_delete


class RebuildLearningResult(ContractModel):
    examples_active: int = 0
    examples_inactive: int = 0
    row_examples_active: int = 0
    index_hash: str = ""
    row_model_hash: str = ""


class ExportCsvResult(ContractModel):
    files: list[str] = Field(default_factory=list)
    row_count: int = 0
    encoding: str = "utf8_bom"
    target_dir: str = ""


class LockState(ContractModel):
    locked: bool = False
    owned: bool = False
    holder_workstation: str = ""
    holder_pid: int = 0
    acquired_utc: str = ""
    heartbeat_utc: str = ""
    stale: bool = False


class AppOpenResult(ContractModel):
    lock_acquired: bool = False
    read_only: bool = False
    lock: Optional[LockState] = None
    snapshot_pulled: bool = False
    pending_pushed: bool = False
    warnings: list[str] = Field(default_factory=list)


class AppCloseResult(ContractModel):
    snapshot_pushed: bool = False
    pending: bool = False
    lock_released: bool = False
    warnings: list[str] = Field(default_factory=list)


class OcrHealth(ContractModel):
    engine: str = "none"
    available: bool = False
    detail: str = ""


class LlmHealth(ContractModel):
    enabled: bool = False
    model_path: str = ""
    model_present: bool = False
    model_sha256_ok: Optional[bool] = None
    server_binary_present: bool = False


class LearningHealth(ContractModel):
    examples_active: int = 0
    row_examples_active: int = 0
    sessions: int = 0


class HealthResult(ContractModel):
    app_version: str
    schema_version: str
    db_schema_version: int
    python_version: str
    platform: str
    data_dir: str
    db_path: str
    ocr: OcrHealth
    llm: LlmHealth
    learning: LearningHealth
    lock: Optional[LockState] = None
    offline_guard: bool = False
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Envelopes
# --------------------------------------------------------------------------

PAYLOAD_MODELS: dict[str, type[ContractModel]] = {
    "list_sheets": ListSheetsPayload,
    "analyze": AnalyzePayload,
    "apply_revision": ApplyRevisionPayload,
    "row_event": RowEventPayload,
    "confirm_cells": ConfirmCellsPayload,
    "undo": UndoPayload,
    "rebuild_learning": RebuildLearningPayload,
    "export_csv": ExportCsvPayload,
    "app_open": AppOpenPayload,
    "app_close": AppClosePayload,
    "health": HealthPayload,
}

RESULT_MODELS: dict[str, type[ContractModel]] = {
    "list_sheets": ListSheetsResult,
    "analyze": AnalyzeResult,
    "apply_revision": ApplyRevisionResult,
    "row_event": RowEventResult,
    "confirm_cells": ConfirmCellsResult,
    "undo": UndoResult,
    "rebuild_learning": RebuildLearningResult,
    "export_csv": ExportCsvResult,
    "app_open": AppOpenResult,
    "app_close": AppCloseResult,
    "health": HealthResult,
}


class JobRequest(ContractModel):
    schema_version: str = SCHEMA_VERSION
    job_id: str = Field(default_factory=new_id)
    kind: RequestKind
    created_utc: datetime = Field(default_factory=utc_now)
    payload: dict

    @field_validator("schema_version")
    @classmethod
    def _compatible(cls, v: str) -> str:
        if v.split(".")[0] != SCHEMA_VERSION.split(".")[0]:
            raise ValueError(
                f"Inkompatible schema_version {v!r}; erwartet {SCHEMA_VERSION!r}"
            )
        return v

    def typed_payload(self) -> ContractModel:
        model = PAYLOAD_MODELS[self.kind]
        return model.model_validate(self.payload)


class JobResponse(ContractModel):
    schema_version: str = SCHEMA_VERSION
    job_id: str
    kind: RequestKind
    ok: bool
    error: Optional[ErrorInfo] = None
    result: Optional[dict] = None
    finished_utc: datetime = Field(default_factory=utc_now)

    def typed_result(self) -> Optional[ContractModel]:
        if self.result is None:
            return None
        return RESULT_MODELS[self.kind].model_validate(self.result)


class JobProgress(ContractModel):
    schema_version: str = SCHEMA_VERSION
    job_id: str
    phase: str = "start"
    percent: int = Field(default=0, ge=0, le=100)
    message: str = ""
    cancellable: bool = True
    done: bool = False
    updated_utc: datetime = Field(default_factory=utc_now)


def make_response(
    request: JobRequest,
    result: ContractModel | None = None,
    error: ErrorInfo | None = None,
) -> JobResponse:
    return JobResponse(
        job_id=request.job_id,
        kind=request.kind,
        ok=error is None,
        error=error,
        result=None if result is None else result.model_dump(mode="json"),
    )

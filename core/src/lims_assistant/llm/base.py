"""LLM-Adapter-Schnittstelle: lokal, schema-beschraenkt, austauschbar."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class LlmRowTask:
    row_ref: int                       # Index innerhalb des Aufrufs
    source_text: str                   # Rohzeile (untrusted data)
    bez1_context: str = ""
    missing_fields: list[str] = field(default_factory=list)
    current: dict[str, str] = field(default_factory=dict)


@dataclass
class LlmSuggestion:
    row_ref: int
    fields: dict[str, str] = field(default_factory=dict)


class LlmAdapter(Protocol):
    name: str

    def available(self) -> tuple[bool, str]: ...

    def suggest(self, tasks: list[LlmRowTask]) -> list[LlmSuggestion]: ...

    def close(self) -> None: ...


MAX_VALUE_LEN = 80


def sanitize_suggestion(fields: dict[str, str]) -> dict[str, str]:
    """Werte des Modells strikt begrenzen und bereinigen."""
    from lims_assistant.domain.entities import FIELDS
    from lims_assistant.textutil import sanitize_lims_value

    out: dict[str, str] = {}
    for key, value in fields.items():
        if key not in FIELDS:
            continue
        clean = sanitize_lims_value(str(value))[:MAX_VALUE_LEN]
        if clean:
            out[key] = clean
    return out

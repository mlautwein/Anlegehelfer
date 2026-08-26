"""Deterministischer Fake-Adapter fuer Tests und Benchmark-Trockenlaeufe."""

from __future__ import annotations

from lims_assistant.llm.base import LlmRowTask, LlmSuggestion, sanitize_suggestion


class FakeLlm:
    """Gibt konfigurierte Vorschlaege zurueck; ohne Konfiguration nichts.

    mapping: {substring_der_zeile: {Feld: Wert}} - der erste passende Eintrag
    liefert die Felder. So lassen sich Modellantworten in Tests exakt steuern,
    einschliesslich boeswilliger Antworten (Robustheitstests).
    """

    name = "fake"

    def __init__(self, mapping: dict[str, dict[str, str]] | None = None, *, raw: bool = False) -> None:
        self.mapping = mapping or {}
        self.raw = raw  # True: Sanitizing im Adapter abschalten (Robustheitstest)
        self.calls: list[list[LlmRowTask]] = []

    def available(self) -> tuple[bool, str]:
        return True, "fake"

    def suggest(self, tasks: list[LlmRowTask]) -> list[LlmSuggestion]:
        self.calls.append(list(tasks))
        out: list[LlmSuggestion] = []
        for task in tasks:
            for needle, fields in self.mapping.items():
                if needle in task.source_text:
                    payload = dict(fields) if self.raw else sanitize_suggestion(fields)
                    restricted = {
                        k: v for k, v in payload.items() if k in task.missing_fields
                    } if not self.raw else payload
                    if restricted:
                        out.append(LlmSuggestion(row_ref=task.row_ref, fields=restricted))
                    break
        return out

    def close(self) -> None:
        return None

"""JSON-Schema fuer die schema-beschraenkte Modellausgabe (llama.cpp).

llama.cpp-Server unterstuetzt response_format=json_schema und erzwingt die
Struktur per Grammatik. Zusaetzlich validiert der Kern jede Antwort erneut
mit Pydantic (extra='forbid') - doppelte Absicherung gegen freie Texte.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

LLM_ROWS_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "row_ref": {"type": "integer"},
                    "Bez1": {"type": "string", "maxLength": 80},
                    "Bez2": {"type": "string", "maxLength": 80},
                    "B3": {"type": "string", "maxLength": 80},
                    "B4": {"type": "string", "maxLength": 80},
                    "Untersuchungsart": {"type": "string", "maxLength": 80},
                },
                "required": ["row_ref"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["rows"],
    "additionalProperties": False,
}


class LlmRowOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    row_ref: int
    Bez1: str = ""
    Bez2: str = ""
    B3: str = ""
    B4: str = ""
    Untersuchungsart: str = ""

    def field_map(self) -> dict[str, str]:
        return {
            "Bez1": self.Bez1,
            "Bez2": self.Bez2,
            "B3": self.B3,
            "B4": self.B4,
            "Untersuchungsart": self.Untersuchungsart,
        }


class LlmRowsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: list[LlmRowOut] = Field(default_factory=list)

"""Fachliche Konstanten und Aufzaehlungen."""

from __future__ import annotations

from enum import Enum

# Genau diese fuenf sichtbaren Fachspalten, in dieser Reihenfolge.
FIELDS: tuple[str, ...] = ("Bez1", "Bez2", "B3", "B4", "Untersuchungsart")

EXPORT_FILENAMES: tuple[str, ...] = (
    "Bez1.csv",
    "Bez2.csv",
    "B3.csv",
    "B4.csv",
    "Untersuchungsart.csv",
)


class Provenance(str, Enum):
    """Woher ein Feldwert stammt (intern; sichtbar ist nur gelb)."""

    DIRECT = "direct"        # klar zugeordnete Dokumentstelle, nur normalisiert
    STRUCTURE = "structure"  # aus Dokument-/Tabellenstruktur (z. B. Spaltenkopf, Objektkontext)
    RETRIEVAL = "retrieval"  # aehnlicher bestaetigter Lernfall
    LLM = "llm"              # lokales Sprachmodell
    HINT = "hint"            # Zusatzinformationen des Imports (immer gelb)
    EMPTY = "empty"          # kein Wert ermittelt
    USER = "user"            # direkte Benutzereingabe/-korrektur


class RowOrigin(str, Enum):
    AUTO = "auto"      # vom Kern erkannte Probenzeile
    MANUAL = "manual"  # vom Benutzer hinzugefuegt


class ConfirmationType(str, Enum):
    EXPORT = "export"
    COPY_COLUMN = "copy_column"
    COPY_SELECTION = "copy_selection"


class LearningTarget(str, Enum):
    """Zielraum eines Lernbeispiels."""

    FIELD = "field"       # Freitext-Zielwert je Feld
    ROW = "row"           # Probenzeile ja/nein (binaer)

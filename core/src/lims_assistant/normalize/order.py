"""Sortierlogik: optional Bez1 -> Etage -> Raum, Quellreihenfolge wiederherstellbar.

Die VBA-Seite spiegelt exakt diese Logik (modErgebnisse.SortRows); diese
Referenzimplementierung ist testbar und dokumentiert das Verhalten.
"""

from __future__ import annotations

import re

from lims_assistant.extract.patterns import etage_rank, natural_key
from lims_assistant.textutil import sanitize_lims_value

_BEZ2_ETAGE_RE = re.compile(
    r"^(EG|UG|KG|DG|ZG|\d{1,2}\. OG|\d{1,2}\. UG|Ebene \d{1,3})(?:,|$)"
)


def split_bez2(bez2: str) -> tuple[str, str]:
    """Zerlegt kanonisches Bez2 in (Etage, Rest) fuer die Sortierung."""
    value = sanitize_lims_value(bez2)
    m = _BEZ2_ETAGE_RE.match(value)
    if m:
        etage = m.group(1)
        rest = value[m.end() :].lstrip(", ")
        return etage, rest
    return "", value


def sort_key(bez1: str, bez2: str) -> tuple:
    etage, rest = split_bez2(bez2)
    return (
        natural_key(bez1),
        etage_rank(etage),
        natural_key(rest),
    )


def sorted_permutation(rows: list[tuple[str, str]]) -> list[int]:
    """Stabile Permutation (Indizes) fuer Zeilen als (Bez1, Bez2)-Tupel."""
    return sorted(range(len(rows)), key=lambda i: sort_key(rows[i][0], rows[i][1]))

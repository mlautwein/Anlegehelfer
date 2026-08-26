"""Referenzlogik fuer den Kopiertext der Spalten-Buttons (VBA spiegelt sie).

Regeln: keine Ueberschrift, Werte zeilenweise, leere Zellen bleiben leere
Zeilen an identischer Position, CRLF zwischen den Zeilen, kein abschliessender
Zeilenumbruch (n Werte => n Zeilen beim Einfuegen ins LIMS-Grid).
"""

from __future__ import annotations

from lims_assistant.textutil import sanitize_lims_value

CRLF = "\r\n"


def column_copy_text(values: list[str]) -> str:
    return CRLF.join(sanitize_lims_value(v) for v in values)

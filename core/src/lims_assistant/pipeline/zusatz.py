"""Auswertung der importbezogenen Zusatzinformationen (nur Hinweis, nie Wahrheit).

Aus dem Zusatztext abgeleitete Feldwerte fuellen ausschliesslich leere Felder
und werden in der Fusion immer als unsicher (gelb) markiert.
"""

from __future__ import annotations

import re

from lims_assistant.extract import vocab
from lims_assistant.extract.features import extract_features
from lims_assistant.textutil import fold_for_match, sanitize_lims_value

_HAUS_RE = re.compile(
    r"(?i)(?<![\wäöüß])((?:haus|geb(?:ä|ae)ude|objekt|station)\s+[\wäöüß.-]{1,20})"
)


def hint_fields(hint_text: str) -> dict[str, str]:
    """Extrahiert vorsichtige Feldkandidaten aus dem Zusatztext."""
    hint = sanitize_lims_value(hint_text)
    if not hint:
        return {}
    folded = fold_for_match(hint)
    out: dict[str, str] = {}

    unt = vocab.match_vocab(folded, vocab.UNTERSUCHUNG_MAP)
    if unt:
        out["Untersuchungsart"] = unt

    kalt = vocab.any_token(folded, vocab.MEDIUM_KALT)
    warm = vocab.any_token(folded, vocab.MEDIUM_WARM)
    if kalt != warm:  # nur bei eindeutigem Hinweis
        out["B4"] = "Kaltwasser" if kalt else "Warmwasser"

    m = _HAUS_RE.search(hint)
    if m:
        out["Bez1"] = sanitize_lims_value(m.group(1))
    else:
        # Erster Komma-Abschnitt ohne fachliche Signale als Objektname werten.
        first = sanitize_lims_value(hint.split(",")[0])
        if 3 <= len(first) <= 60:
            f = extract_features(first, allow_fuzzy=False)
            if f.signal_count() == 0 and not vocab.match_vocab(
                fold_for_match(first), vocab.UNTERSUCHUNG_MAP
            ):
                out["Bez1"] = first
    return out

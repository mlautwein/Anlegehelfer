"""Binaerer Zeilendetektor: 'Probenstelle' vs. 'keine Probenstelle'.

Multinomialer Naive Bayes ueber denselben n-Gramm-Merkmalen wie der Index.
Inkrementell im Sinne des Produkts: Er wird bei jedem Start/Rebuild aus den
aktiven Zeilenbeispielen neu aufgebaut (Sekundenbruchteile bei dieser
Datenmenge) und ist damit exakt reproduzierbar und rollbackfaehig.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter

from lims_assistant.learn.index import featurize

MIN_PER_CLASS = 3


class RowClassifier:
    def __init__(self) -> None:
        self.counts: dict[str, Counter] = {"1": Counter(), "0": Counter()}
        self.totals: dict[str, int] = {"1": 0, "0": 0}
        self.docs: dict[str, int] = {"1": 0, "0": 0}
        self.vocab: set[str] = set()
        self._items: list[tuple[str, str]] = []

    def build(self, items: list[tuple[str, str]]) -> None:
        """items: (text, label '1'/'0') in deterministischer Reihenfolge."""
        self.__init__()
        self._items = list(items)
        for text, label in items:
            if label not in ("0", "1"):
                continue
            feats = featurize(text)
            self.docs[label] += 1
            for key, tf in feats.items():
                self.counts[label][key] += tf
                self.totals[label] += tf
                self.vocab.add(key)

    def ready(self) -> bool:
        return self.docs["1"] >= MIN_PER_CLASS and self.docs["0"] >= MIN_PER_CLASS

    def probability(self, text: str) -> float | None:
        """P(Probenstelle | Text); None solange zu wenig Beispiele vorliegen."""
        if not self.ready():
            return None
        feats = featurize(text)
        if not feats:
            return None
        v = len(self.vocab) or 1
        log_p = {}
        total_docs = self.docs["1"] + self.docs["0"]
        for label in ("1", "0"):
            lp = math.log((self.docs[label] + 1) / (total_docs + 2))
            denom = self.totals[label] + v
            for key, tf in feats.items():
                lp += tf * math.log((self.counts[label][key] + 1) / denom)
            log_p[label] = lp
        m = max(log_p.values())
        e1 = math.exp(log_p["1"] - m)
        e0 = math.exp(log_p["0"] - m)
        return e1 / (e1 + e0)

    def content_hash(self) -> str:
        h = hashlib.sha256()
        for text, label in sorted(self._items):
            h.update(label.encode("ascii"))
            h.update(b"\x1f")
            h.update(text.encode("utf-8"))
            h.update(b"\x1e")
        return h.hexdigest()

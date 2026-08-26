"""Reproduzierbarer TF-IDF-Aehnlichkeitsindex (reines Python, deterministisch).

Wort- und Zeichen-n-Gramm-Merkmale; Kosinus-Aehnlichkeit; kein externer
Vektorspeicher. Der Index wird bei jedem Prozessstart vollstaendig aus den
aktiven Lernbeispielen aufgebaut - damit ist NFR-010 (Reproduzierbarkeit)
konstruktiv erfuellt.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass

from lims_assistant.textutil import fold_for_match


def featurize(text: str) -> Counter:
    """Zeichen-3-Gramme + Wort-Uni-/Bigramme auf gefaltetem Text."""
    folded = fold_for_match(text)
    feats: Counter = Counter()
    if not folded:
        return feats
    words = folded.split()
    for w in words:
        feats[f"w:{w}"] += 1
    for a, b in zip(words, words[1:]):
        feats[f"b:{a} {b}"] += 1
    padded = f"  {folded}  "
    for i in range(len(padded) - 2):
        feats[f"c:{padded[i:i+3]}"] += 1
    return feats


@dataclass
class IndexedDoc:
    doc_id: str
    label: str
    weights: dict[str, float]  # L2-normalisiert


class TfIdfIndex:
    def __init__(self) -> None:
        self.docs: list[IndexedDoc] = []
        self.idf: dict[str, float] = {}

    def build(self, items: list[tuple[str, str, str]]) -> None:
        """items: (doc_id, input_text, label) - Reihenfolge deterministisch."""
        self.docs = []
        self.idf = {}
        feats_per_doc: list[tuple[str, str, Counter]] = []
        df: Counter = Counter()
        for doc_id, text, label in items:
            feats = featurize(text)
            feats_per_doc.append((doc_id, label, feats))
            for key in feats:
                df[key] += 1
        n = len(feats_per_doc)
        if n == 0:
            return
        self.idf = {
            key: math.log((1 + n) / (1 + count)) + 1.0 for key, count in df.items()
        }
        for doc_id, label, feats in feats_per_doc:
            weights = {
                key: (1.0 + math.log(tf)) * self.idf[key] for key, tf in feats.items()
            }
            norm = math.sqrt(sum(v * v for v in weights.values())) or 1.0
            self.docs.append(
                IndexedDoc(
                    doc_id=doc_id,
                    label=label,
                    weights={k: v / norm for k, v in weights.items()},
                )
            )

    def query(self, text: str, top_k: int = 5) -> list[tuple[str, str, float]]:
        """Rueckgabe: [(doc_id, label, similarity)] absteigend, deterministisch."""
        feats = featurize(text)
        if not feats or not self.docs:
            return []
        weights = {}
        for key, tf in feats.items():
            idf = self.idf.get(key)
            if idf is None:
                continue
            weights[key] = (1.0 + math.log(tf)) * idf
        norm = math.sqrt(sum(v * v for v in weights.values()))
        if norm == 0:
            return []
        query_w = {k: v / norm for k, v in weights.items()}
        scored: list[tuple[float, str, str]] = []
        for doc in self.docs:
            sim = 0.0
            small, large = (
                (query_w, doc.weights)
                if len(query_w) <= len(doc.weights)
                else (doc.weights, query_w)
            )
            for key, val in small.items():
                other = large.get(key)
                if other:
                    sim += val * other
            if sim > 0:
                scored.append((sim, doc.doc_id, doc.label))
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [(doc_id, label, round(sim, 6)) for sim, doc_id, label in scored[:top_k]]

    def content_hash(self) -> str:
        h = hashlib.sha256()
        for doc in sorted(self.docs, key=lambda d: d.doc_id):
            h.update(doc.doc_id.encode("utf-8"))
            h.update(b"\x1f")
            h.update(doc.label.encode("utf-8"))
            h.update(b"\x1e")
        return h.hexdigest()

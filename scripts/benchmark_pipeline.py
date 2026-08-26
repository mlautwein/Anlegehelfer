#!/usr/bin/env python3
"""Laufzeit-/RAM-/Qualitaets-Benchmark der Analysepipeline (ohne LLM).

Misst je Fixture: Dauer (p50/p95 ueber N Laeufe), Peak-RSS des
Analyseprozesses, Zeilen-Precision/Recall/F1 gegen Gold, Feld-Exact-Match,
normalisierte Treffer, Zeichen-Edit-Distanz und Gelb-Quote.

Aufruf: python scripts/benchmark_pipeline.py [--runs 3] [--out docs/benchmarks/dev.md]
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "core" / "src"
FIXTURES = REPO / "fixtures" / "synthetic"
sys.path.insert(0, str(SRC))

from lims_assistant.domain.entities import FIELDS  # noqa: E402
from lims_assistant.textutil import fold_for_match, levenshtein  # noqa: E402

CASES = [
    ("klinik_digital.pdf", "pdf", None),
    ("seniorenresidenz_freitext.pdf", "pdf", None),
    ("schule_scan.pdf", "pdf", None),
    ("wohnhaus.xlsx", "excel", ["Wohnhaus Gartenstr. 12"]),
]


def run_analyze_subprocess(source_name: str, stype: str, sheets):
    """Analyse in frischem Prozess (realistische Peak-RSS-Messung)."""
    with tempfile.TemporaryDirectory() as td:
        job_dir = Path(td) / "job"
        job_dir.mkdir()
        payload_source = {"type": stype, "paths": [str(FIXTURES / source_name)]}
        if sheets:
            payload_source["sheets"] = sheets
        (job_dir / "request.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "job_id": str(uuid.uuid4()),
                    "kind": "analyze",
                    "created_utc": "2026-01-01T00:00:00Z",
                    "payload": {"sources": [payload_source]},
                }
            ),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SRC)
        env["LIMS_DATA_DIR"] = str(Path(td) / "data")
        before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        t0 = time.monotonic()
        subprocess.run(
            [sys.executable, "-m", "lims_assistant.jobs.cli", "run-job", "--job-dir", str(job_dir)],
            env=env,
            check=True,
            capture_output=True,
            timeout=600,
        )
        duration = time.monotonic() - t0
        after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        peak_kb = max(after, before)  # ru_maxrss: Linux=KB, macOS=Bytes
        if sys.platform == "darwin":
            peak_kb = peak_kb / 1024
        resp = json.loads((job_dir / "response.json").read_text(encoding="utf-8"))
        return resp, duration, peak_kb / 1024.0  # MB


def evaluate(rows, gold_rows):
    n_pred, n_gold = len(rows), len(gold_rows)
    matched = min(n_pred, n_gold)
    precision = matched / n_pred if n_pred else 0.0
    recall = matched / n_gold if n_gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    exact = {f: 0 for f in FIELDS}
    norm = {f: 0 for f in FIELDS}
    dist = {f: [] for f in FIELDS}
    yellow = 0
    cells = 0
    for row, gold in zip(rows, gold_rows):
        for f in FIELDS:
            got = row["fields"][f]["value"]
            want = gold[f]
            cells += 1
            if row["fields"][f]["is_uncertain"]:
                yellow += 1
            if got == want:
                exact[f] += 1
            if fold_for_match(got) == fold_for_match(want):
                norm[f] += 1
            dist[f].append(levenshtein(got, want))
    return {
        "rows_pred": n_pred,
        "rows_gold": n_gold,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "exact": {f: f"{exact[f]}/{matched}" for f in FIELDS},
        "exact_rate": round(sum(exact.values()) / (matched * 5), 3) if matched else 0.0,
        "norm_rate": round(sum(norm.values()) / (matched * 5), 3) if matched else 0.0,
        "edit_mean": round(
            statistics.mean([d for f in FIELDS for d in dist[f]] or [0]), 2
        ),
        "yellow_rate": round(yellow / cells, 3) if cells else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    gold = json.loads((FIXTURES / "gold" / "expected.json").read_text(encoding="utf-8"))
    report_lines = [
        "# Pipeline-Benchmark (Entwicklungsumgebung)",
        "",
        f"- Laeufe je Fall: {args.runs} (frischer Prozess je Lauf; Peak-RSS des Kindprozesses)",
        f"- Python: {sys.version.split()[0]}, Plattform: {sys.platform}",
        "- Hinweis: Werte der Entwicklungsmaschine; Zielhardware-Messung (Windows 11 x64) steht aus.",
        "",
        "| Fall | Zeilen (erkannt/gold) | P | R | F1 | Exact | Norm. | Edit Ø | Gelb | p50 | p95 | Peak-RAM |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    results = {}
    for name, stype, sheets in CASES:
        durations = []
        peaks = []
        last_resp = None
        for _ in range(args.runs):
            resp, duration, peak_mb = run_analyze_subprocess(name, stype, sheets)
            durations.append(duration)
            peaks.append(peak_mb)
            last_resp = resp
        if not last_resp.get("ok"):
            print(f"{name}: FEHLER {last_resp.get('error')}")
            continue
        rows = last_resp["result"]["rows"]
        stats = (
            evaluate(rows, gold[name]) if name in gold else {
                "rows_pred": len(rows), "rows_gold": "-", "precision": "-",
                "recall": "-", "f1": "-", "exact_rate": "-", "norm_rate": "-",
                "edit_mean": "-", "yellow_rate": "-",
            }
        )
        durations.sort()
        p50 = durations[len(durations) // 2]
        p95 = durations[min(len(durations) - 1, int(len(durations) * 0.95))]
        results[name] = {**stats, "p50_s": round(p50, 2), "p95_s": round(p95, 2), "peak_mb": round(max(peaks), 1)}
        report_lines.append(
            f"| {name} | {stats['rows_pred']}/{stats['rows_gold']} | {stats['precision']} | "
            f"{stats['recall']} | {stats['f1']} | {stats['exact_rate']} | {stats['norm_rate']} | "
            f"{stats['edit_mean']} | {stats['yellow_rate']} | {p50:.2f}s | {p95:.2f}s | "
            f"{max(peaks):.0f} MB |"
        )
        print(f"{name}: {results[name]}")

    report = "\n".join(report_lines) + "\n"
    if args.out:
        out = REPO / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"\nBericht: {out}")
    else:
        print("\n" + report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

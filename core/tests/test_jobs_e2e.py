"""End-to-end ueber das echte Dateiprotokoll und die echte CLI (Subprozess).

Dies ist der synthetische Pfad ohne Mocks: request.json -> lims-core ->
progress.json/response.json -> validierte Ergebniszeilen.
"""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "core" / "src"


def _run_cli(args, data_dir, extra_env=None):
    env = os.environ.copy()
    env["LIMS_DATA_DIR"] = str(data_dir)
    env["PYTHONPATH"] = str(SRC)
    env.pop("LIMS_ALLOW_NET", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "lims_assistant.jobs.cli", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )


def _write_request(job_dir: Path, kind: str, payload: dict) -> str:
    job_dir.mkdir(parents=True, exist_ok=True)
    job_id = str(uuid.uuid4())
    (job_dir / "request.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "job_id": job_id,
                "kind": kind,
                "created_utc": "2026-08-26T00:00:00Z",
                "payload": payload,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return job_id


def test_analyze_job_end_to_end(tmp_path, fixtures_dir):
    from lims_assistant.contracts.models import JobResponse

    data_dir = tmp_path / "data"
    job_dir = tmp_path / "job1"
    job_id = _write_request(
        job_dir,
        "analyze",
        {
            "sources": [
                {"type": "pdf", "paths": [str(fixtures_dir / "klinik_digital.pdf")]}
            ]
        },
    )
    proc = _run_cli(["run-job", "--job-dir", str(job_dir)], data_dir)
    assert proc.returncode == 0, proc.stderr

    progress = json.loads((job_dir / "progress.json").read_text(encoding="utf-8"))
    assert progress["done"] is True and progress["percent"] == 100

    raw = json.loads((job_dir / "response.json").read_text(encoding="utf-8"))
    resp = JobResponse.model_validate(raw)  # strenge Schemapruefung
    assert resp.ok and resp.job_id == job_id
    result = resp.typed_result()
    assert len(result.rows) == 14
    for row in result.rows:
        assert set(row.fields) == {"Bez1", "Bez2", "B3", "B4", "Untersuchungsart"}

    # Folge-Job im selben Datenverzeichnis: Korrektur via Protokoll
    job2 = tmp_path / "job2"
    _write_request(
        job2,
        "apply_revision",
        {
            "session_id": result.session_id,
            "row_id": result.rows[0].row_id,
            "field": "B3",
            "old_value": result.rows[0].fields["B3"].value,
            "new_value": "Bad, Waschtisch, Einhandmischarmatur",
            "client_event_id": "e2e-rev",
        },
    )
    proc2 = _run_cli(["run-job", "--job-dir", str(job2)], data_dir)
    assert proc2.returncode == 0
    resp2 = json.loads((job2 / "response.json").read_text(encoding="utf-8"))
    assert resp2["ok"] is True


def test_cancel_flag_bricht_analyse_ab(tmp_path, fixtures_dir):
    data_dir = tmp_path / "data"
    job_dir = tmp_path / "job-cancel"
    _write_request(
        job_dir,
        "analyze",
        {
            "sources": [
                {"type": "pdf", "paths": [str(fixtures_dir / "klinik_digital.pdf")]}
            ]
        },
    )
    (job_dir / "cancel.flag").write_text("1")
    proc = _run_cli(["run-job", "--job-dir", str(job_dir)], data_dir)
    assert proc.returncode == 0
    resp = json.loads((job_dir / "response.json").read_text(encoding="utf-8"))
    assert resp["ok"] is False
    assert resp["error"]["code"] == "cancelled"

    # Abbruch hinterlaesst keine halbfertigen Zeilen
    health_job = tmp_path / "job-h"
    _write_request(health_job, "health", {})
    _run_cli(["run-job", "--job-dir", str(health_job)], data_dir)
    h = json.loads((health_job / "response.json").read_text(encoding="utf-8"))
    assert h["result"]["learning"]["sessions"] == 0


def test_offline_guard_im_produktivmodus_aktiv(tmp_path):
    data_dir = tmp_path / "data"
    proc = _run_cli(["health"], data_dir)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["result"]["offline_guard"] is True


def test_defekte_requestdatei_ergibt_saubere_fehlerantwort(tmp_path):
    data_dir = tmp_path / "data"
    job_dir = tmp_path / "job-bad"
    job_dir.mkdir()
    (job_dir / "request.json").write_text("{kaputt", encoding="utf-8")
    proc = _run_cli(["run-job", "--job-dir", str(job_dir)], data_dir)
    assert proc.returncode == 2
    resp = json.loads((job_dir / "response.json").read_text(encoding="utf-8"))
    assert resp["ok"] is False and resp["error"]["code"] == "bad_request"


def test_keine_originaldateien_im_datenverzeichnis(tmp_path, fixtures_dir):
    """A-10: Originale duerfen weder im Daten- noch im Tempordner verbleiben."""
    data_dir = tmp_path / "data"
    job_dir = tmp_path / "job-orig"
    _write_request(
        job_dir,
        "analyze",
        {
            "sources": [
                {"type": "pdf", "paths": [str(fixtures_dir / "klinik_digital.pdf")]},
                {
                    "type": "image_set",
                    "paths": [str(fixtures_dir / "schule_scan_sauber.png")],
                },
            ]
        },
    )
    proc = _run_cli(["run-job", "--job-dir", str(job_dir)], data_dir)
    assert proc.returncode == 0
    suffixes = {".pdf", ".png", ".jpg", ".jpeg", ".heic", ".xlsx", ".xls", ".xlsm"}
    offenders = [
        p
        for p in Path(data_dir).rglob("*")
        if p.is_file() and p.suffix.lower() in suffixes
    ]
    assert offenders == [], f"Originaldateien im Datenverzeichnis: {offenders}"

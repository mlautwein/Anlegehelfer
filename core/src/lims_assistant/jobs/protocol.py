"""Dateibasiertes Jobprotokoll (request/progress/response, atomar).

Excel schreibt request.json und startet die EXE. Die EXE schreibt
progress.json fortlaufend atomar und zum Schluss response.json (ebenfalls
atomar). Abbruch: Excel legt cancel.flag in das Jobverzeichnis.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from lims_assistant.contracts.models import JobProgress, JobRequest, JobResponse

REQUEST_NAME = "request.json"
PROGRESS_NAME = "progress.json"
RESPONSE_NAME = "response.json"
CANCEL_NAME = "cancel.flag"


def atomic_write_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)


def read_request(job_dir: str | Path) -> JobRequest:
    raw = json.loads(
        (Path(job_dir) / REQUEST_NAME).read_text(encoding="utf-8-sig")
    )
    return JobRequest.model_validate(raw)


def write_progress(job_dir: str | Path, progress: JobProgress) -> None:
    atomic_write_json(Path(job_dir) / PROGRESS_NAME, progress.model_dump(mode="json"))


def write_response(job_dir: str | Path, response: JobResponse) -> None:
    atomic_write_json(Path(job_dir) / RESPONSE_NAME, response.model_dump(mode="json"))


def cancel_requested(job_dir: str | Path) -> bool:
    return (Path(job_dir) / CANCEL_NAME).exists()

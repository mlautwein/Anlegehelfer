"""Export der JSON-Schemas aller Vertraege nach contracts/schemas/."""

from __future__ import annotations

import json
from pathlib import Path

from lims_assistant.contracts.models import (
    PAYLOAD_MODELS,
    RESULT_MODELS,
    JobProgress,
    JobRequest,
    JobResponse,
)
from lims_assistant.version import SCHEMA_VERSION


def _dump(model) -> dict:
    return model.model_json_schema()


def export_all(out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    def write(name: str, schema: dict) -> None:
        schema = {"$comment": f"schema_version {SCHEMA_VERSION}", **schema}
        path = out_dir / f"{name}.schema.json"
        path.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(str(path))

    write("JobRequest", _dump(JobRequest))
    write("JobResponse", _dump(JobResponse))
    write("JobProgress", _dump(JobProgress))
    for kind, model in sorted(PAYLOAD_MODELS.items()):
        write(f"{kind}.payload", _dump(model))
    for kind, model in sorted(RESULT_MODELS.items()):
        write(f"{kind}.result", _dump(model))
    return written

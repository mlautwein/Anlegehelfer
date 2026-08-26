"""Kommandozeileneinstieg der portablen Core-EXE.

Kommandos sind klein und idempotent. Benutzerdaten (Pfade, Texte) reisen
ausschliesslich in JSON-Dateien, niemals als Shell-Argumente.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lims_assistant import net_guard, paths
from lims_assistant.config import Settings, load_settings
from lims_assistant.contracts.models import JobProgress, JobRequest
from lims_assistant.jobs import protocol
from lims_assistant.jobs.runner import execute, open_db
from lims_assistant.version import APP_VERSION, SCHEMA_VERSION


def _install_guard(settings: Settings) -> None:
    import os

    if settings.offline_strict and os.environ.get("LIMS_ALLOW_NET") != "1":
        net_guard.install()


def _cmd_run_job(args, settings: Settings) -> int:
    job_dir = Path(args.job_dir)
    try:
        request = protocol.read_request(job_dir)
    except Exception as exc:  # noqa: BLE001 - Protokollfehler sauber melden
        protocol.atomic_write_json(
            job_dir / protocol.RESPONSE_NAME,
            {
                "schema_version": SCHEMA_VERSION,
                "job_id": "unknown",
                "kind": "health",
                "ok": False,
                "error": {
                    "code": "bad_request",
                    "message": "request.json unlesbar oder ungueltig.",
                    "detail": f"{type(exc).__name__}: {exc}",
                },
                "result": None,
                "finished_utc": "1970-01-01T00:00:00Z",
            },
        )
        return 2

    def progress(phase: str, percent: int, message: str) -> None:
        protocol.write_progress(
            job_dir,
            JobProgress(
                job_id=request.job_id,
                phase=phase,
                percent=max(0, min(100, int(percent))),
                message=message,
                cancellable=request.kind == "analyze",
            ),
        )

    def cancelled() -> bool:
        return protocol.cancel_requested(job_dir)

    progress("start", 0, "Job angenommen")
    response = execute(
        request, settings, progress=progress, cancelled=cancelled
    )
    protocol.write_response(job_dir, response)
    protocol.write_progress(
        job_dir,
        JobProgress(
            job_id=request.job_id,
            phase="fertig" if response.ok else "fehler",
            percent=100,
            message="" if response.ok else (response.error.message if response.error else ""),
            cancellable=False,
            done=True,
        ),
    )
    return 0


def _cmd_health(args, settings: Settings) -> int:
    request = JobRequest(kind="health", payload={})
    response = execute(request, settings)
    print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if response.ok else 1


def _cmd_rebuild(args, settings: Settings) -> int:
    request = JobRequest(kind="rebuild_learning", payload={})
    response = execute(request, settings)
    print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if response.ok else 1


def _cmd_heartbeat(args, settings: Settings) -> int:
    from lims_assistant.jobs.runner import _load_lock  # interner Helfer

    lock = _load_lock(settings)
    if lock is None:
        print("kein aktiver Lock")
        return 0
    ok = lock.heartbeat()
    print("heartbeat ok" if ok else "heartbeat fehlgeschlagen (Lock verloren)")
    return 0 if ok else 1


def _cmd_sweep(args, settings: Settings) -> int:
    removed = paths.sweep_stale(max_age_days=args.max_age_days)
    print(f"{removed} Eintraege entfernt")
    return 0


def _cmd_export_schemas(args, settings: Settings) -> int:
    from lims_assistant.contracts.export_schemas import export_all

    written = export_all(Path(args.out))
    for name in written:
        print(name)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lims-core",
        description=f"LIMS-Probenassistent Rechenkern {APP_VERSION} (offline)",
    )
    parser.add_argument("--config", help="Pfad zu config.json", default=None)
    parser.add_argument(
        "--version",
        action="version",
        version=f"lims-core {APP_VERSION} (Jobvertrag {SCHEMA_VERSION})",
        help="Version von Kern und Jobvertrag ausgeben",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run-job", help="Jobdatei ausfuehren (request.json im Jobordner)")
    p.add_argument("--job-dir", required=True)
    p.set_defaults(func=_cmd_run_job)

    p = sub.add_parser("health", help="Selbstauskunft als JSON")
    p.set_defaults(func=_cmd_health)

    p = sub.add_parser("rebuild", help="Lernindizes aus aktiver Historie neu aufbauen")
    p.set_defaults(func=_cmd_rebuild)

    p = sub.add_parser("heartbeat", help="Lock-Heartbeat aktualisieren")
    p.set_defaults(func=_cmd_heartbeat)

    p = sub.add_parser("sweep", help="verwaiste Temporaerdaten bereinigen")
    p.add_argument("--max-age-days", type=float, default=3.0)
    p.set_defaults(func=_cmd_sweep)

    p = sub.add_parser("export-schemas", help="JSON-Schemas der Vertraege exportieren")
    p.add_argument("--out", required=True)
    p.set_defaults(func=_cmd_export_schemas)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(args.config)
    _install_guard(settings)
    paths.ensure_dirs()
    try:
        return int(args.func(args, settings))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())

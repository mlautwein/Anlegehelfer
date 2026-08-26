"""Plattformpfade fuer Arbeitsdaten, Jobs und Temporaerdateien.

Produktiv (Windows): %LOCALAPPDATA%\\LIMS-Probenassistent\\...
Entwicklung (macOS/Linux): ~/.local/share/lims-probenassistent/...
Alle Pfade sind ueber die Umgebungsvariable LIMS_DATA_DIR uebersteuerbar
(wichtig fuer Tests und portable Sonderfaelle).
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

APP_DIR_NAME = "LIMS-Probenassistent"


def data_root() -> Path:
    override = os.environ.get("LIMS_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_DIR_NAME
    return Path.home() / ".local" / "share" / "lims-probenassistent"


def work_dir() -> Path:
    return data_root() / "work"


def jobs_dir() -> Path:
    return data_root() / "jobs"


def tmp_dir() -> Path:
    return data_root() / "tmp"


def logs_dir() -> Path:
    return data_root() / "logs"


def models_cache_dir() -> Path:
    return data_root() / "models-cache"


def local_db_path() -> Path:
    return work_dir() / "lims.sqlite"


def ensure_dirs() -> None:
    for d in (work_dir(), jobs_dir(), tmp_dir(), logs_dir()):
        d.mkdir(parents=True, exist_ok=True)


def new_job_tmp_dir(job_id: str | None = None) -> Path:
    """Job-spezifisches Temporaerverzeichnis (wird im finally geloescht)."""
    ensure_dirs()
    name = job_id or uuid.uuid4().hex
    p = tmp_dir() / f"job-{name}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def sweep_stale(max_age_days: float = 3.0) -> int:
    """Startbereinigung: verwaiste Job-/Tempverzeichnisse entfernen.

    Originaldokumente duerfen niemals dauerhaft in Temp liegen bleiben,
    auch nicht nach Absturz. Rueckgabe: Anzahl entfernter Eintraege.
    """
    import shutil

    removed = 0
    cutoff = time.time() - max_age_days * 86400
    for root in (tmp_dir(), jobs_dir()):
        if not root.exists():
            continue
        for entry in root.iterdir():
            try:
                if entry.stat().st_mtime < cutoff:
                    if entry.is_dir():
                        shutil.rmtree(entry, ignore_errors=True)
                    else:
                        entry.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                continue
    return removed

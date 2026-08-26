"""Snapshot-Synchronisierung: lokaler Arbeitscache <-> gemeinsamer Ordner.

SQLite laeuft nie direkt auf der Netzwerkfreigabe (WAL dort nicht zulaessig).
Ablauf: exklusiver Lock -> kanonischen Snapshot per SHA-256 pruefen und in den
lokalen Cache kopieren -> lokal transaktional arbeiten -> konsistenten
Snapshot per Tempdatei + atomarem Replace zurueckschreiben; Manifest mit Hash
und Schemaversion; rollierende Backups; bei Netzwerkfehler bleibt ein lokaler
Pending-Stand erhalten und wird beim naechsten exklusiven Start gepusht.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from lims_assistant.textutil import sha256_file
from lims_assistant.version import APP_VERSION, DB_SCHEMA_VERSION

SNAPSHOT_NAME = "snapshot.sqlite"
META_NAME = "snapshot.meta.json"
BACKUP_KEEP = 5


class SnapshotError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SnapshotSync:
    def __init__(self, share_dir: str | Path, local_db: str | Path) -> None:
        self.share_data = Path(share_dir) / "data"
        self.backup_dir = self.share_data / "backups"
        self.local_db = Path(local_db)
        self.pending_flag = self.local_db.parent / "pending-sync.flag"

    # ------------------------------------------------------------ Hilfen

    def read_meta(self) -> dict | None:
        try:
            return json.loads((self.share_data / META_NAME).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotError(f"Snapshot-Manifest unlesbar: {exc}") from exc

    def has_pending(self) -> bool:
        return self.pending_flag.exists()

    def _mark_pending(self, reason: str) -> None:
        try:
            self.pending_flag.write_text(
                json.dumps({"reason": reason, "utc": _now_iso()}), encoding="utf-8"
            )
        except OSError:
            pass

    def _clear_pending(self) -> None:
        try:
            self.pending_flag.unlink(missing_ok=True)
        except OSError:
            pass

    # ------------------------------------------------------------ Pull

    def pull(self) -> bool:
        """Kanonischen Snapshot in den lokalen Cache uebernehmen.

        Rueckgabe: True, wenn ein Snapshot uebernommen wurde. Ein lokaler
        Pending-Stand wird niemals ueberschrieben.
        """
        meta = self.read_meta()
        snap = self.share_data / SNAPSHOT_NAME
        if meta is None or not snap.is_file():
            return False
        if self.has_pending():
            # Lokale, noch nicht synchronisierte Aenderungen haben Vorrang.
            return False
        actual = sha256_file(snap)
        if actual != meta.get("db_sha256"):
            raise SnapshotError(
                "Snapshot-Hash stimmt nicht mit Manifest ueberein - zentraler Stand "
                "beschaedigt; letzter Backup-Stand kann wiederhergestellt werden."
            )
        if int(meta.get("db_schema_version", 0)) > DB_SCHEMA_VERSION:
            raise SnapshotError(
                "Zentraler Snapshot hat ein neueres Schema - bitte aktuelle "
                "Programmversion verwenden."
            )
        self.local_db.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.local_db.with_suffix(f".pull-{uuid.uuid4().hex[:8]}")
        shutil.copyfile(snap, tmp)
        os.replace(tmp, self.local_db)
        # WAL-/SHM-Reste eines frueheren lokalen Stands entfernen
        for suffix in ("-wal", "-shm"):
            side = Path(str(self.local_db) + suffix)
            side.unlink(missing_ok=True)
        return True

    # ------------------------------------------------------------ Push

    def _consistent_copy(self, target: Path) -> None:
        """Konsistente Kopie der lokalen DB via SQLite-Backup-API."""
        src = sqlite3.connect(str(self.local_db))
        try:
            dst = sqlite3.connect(str(target))
            try:
                src.backup(dst)
                dst.execute("PRAGMA journal_mode = DELETE")
            finally:
                dst.close()
        finally:
            src.close()

    def push(self) -> bool:
        """Lokalen Stand als kanonischen Snapshot veroeffentlichen.

        Bei jedem Fehler bleibt der letzte gueltige zentrale Stand erhalten
        und lokal wird ein Pending-Snapshot markiert.
        """
        if not self.local_db.is_file():
            return False
        staging = self.local_db.with_suffix(f".push-{uuid.uuid4().hex[:8]}")
        try:
            self._consistent_copy(staging)
            digest = sha256_file(staging)
            meta_old = None
            try:
                meta_old = self.read_meta()
            except SnapshotError:
                meta_old = None

            self.share_data.mkdir(parents=True, exist_ok=True)
            snap = self.share_data / SNAPSHOT_NAME
            meta_path = self.share_data / META_NAME

            # Backup des bisherigen Stands (rollierend)
            if snap.is_file() and meta_old:
                self.backup_dir.mkdir(parents=True, exist_ok=True)
                stamp = (meta_old.get("updated_utc") or _now_iso()).replace(":", "-")
                backup_target = self.backup_dir / f"snapshot-{stamp}.sqlite"
                if not backup_target.exists():
                    shutil.copyfile(snap, backup_target)
                backups = sorted(self.backup_dir.glob("snapshot-*.sqlite"))
                for old in backups[:-BACKUP_KEEP]:
                    old.unlink(missing_ok=True)

            tmp_snap = self.share_data / f".{SNAPSHOT_NAME}.{uuid.uuid4().hex[:8]}.tmp"
            shutil.copyfile(staging, tmp_snap)
            os.replace(tmp_snap, snap)

            meta = {
                "db_sha256": digest,
                "db_schema_version": DB_SCHEMA_VERSION,
                "app_version": APP_VERSION,
                "updated_utc": _now_iso(),
                "sequence": int((meta_old or {}).get("sequence", 0)) + 1,
            }
            tmp_meta = self.share_data / f".{META_NAME}.{uuid.uuid4().hex[:8]}.tmp"
            tmp_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            os.replace(tmp_meta, meta_path)

            self._clear_pending()
            return True
        except (OSError, sqlite3.Error) as exc:
            self._mark_pending(str(exc))
            raise SnapshotError(
                f"Snapshot konnte nicht in den gemeinsamen Ordner geschrieben werden: {exc}. "
                "Der lokale Stand bleibt erhalten und wird beim naechsten Start synchronisiert."
            ) from exc
        finally:
            staging.unlink(missing_ok=True)

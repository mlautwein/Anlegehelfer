"""Exklusiver Schreib-Lock im gemeinsamen Ordner.

- Genau ein schreibender Arbeitsplatz; ein zweiter Start ist nur lesend.
- Lockdatei traegt PC, PID, Zeitstempel, Paket-/Schemaversion und Nonce.
- Ein veralteter Lock (Heartbeat aelter als Timeout) wird NIE automatisch
  uebernommen, sondern nur nach expliziter Benutzerentscheidung
  (takeover_stale) - Vorgabe der Spezifikation Kap. 11.2.
"""

from __future__ import annotations

import json
import os
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path

from lims_assistant.version import APP_VERSION, DB_SCHEMA_VERSION


class LockBusyError(RuntimeError):
    def __init__(self, holder: dict, stale: bool) -> None:
        self.holder = holder
        self.stale = stale
        who = holder.get("workstation", "?")
        super().__init__(
            f"Schreibzugriff belegt durch '{who}'" + (" (veraltet)" if stale else "")
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


class SharedLock:
    FILENAME = "lims.lock"

    def __init__(
        self,
        share_dir: str | Path,
        *,
        workstation: str = "",
        stale_minutes: int = 12,
    ) -> None:
        self.lock_dir = Path(share_dir) / "lock"
        self.path = self.lock_dir / self.FILENAME
        self.workstation = workstation or socket.gethostname()
        self.stale_minutes = stale_minutes
        self.nonce: str | None = None

    # ------------------------------------------------------------ intern

    def _payload(self) -> dict:
        return {
            "workstation": self.workstation,
            "pid": os.getpid(),
            "acquired_utc": _iso(_now()),
            "heartbeat_utc": _iso(_now()),
            "app_version": APP_VERSION,
            "db_schema_version": DB_SCHEMA_VERSION,
            "nonce": self.nonce,
        }

    def read_state(self) -> dict | None:
        try:
            raw = self.path.read_text(encoding="utf-8")
            return json.loads(raw)
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError):
            return {"workstation": "?", "corrupt": True}

    def is_stale(self, state: dict | None) -> bool:
        if not state:
            return False
        hb = state.get("heartbeat_utc") or state.get("acquired_utc")
        if not hb:
            return True
        try:
            ts = datetime.fromisoformat(hb)
        except ValueError:
            return True
        age = (_now() - ts).total_seconds()
        return age > self.stale_minutes * 60

    def _write_atomic(self, payload: dict) -> None:
        tmp = self.path.with_suffix(f".tmp-{uuid.uuid4().hex[:8]}")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    # ------------------------------------------------------------ API

    def acquire(self, *, takeover_stale: bool = False) -> dict:
        """Erwirbt den Lock exklusiv (O_CREAT|O_EXCL). Wirft LockBusyError."""
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.nonce = uuid.uuid4().hex
        payload = self._payload()
        try:
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
            return payload
        except FileExistsError:
            state = self.read_state()
            stale = self.is_stale(state)
            if stale and takeover_stale:
                stale_name = self.path.with_name(
                    f"lims.lock.stale-{_now().strftime('%Y%m%d-%H%M%S')}"
                )
                try:
                    os.replace(self.path, stale_name)
                except OSError:
                    pass
                # zweiter, letzter Versuch exklusiv
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
                    os.fsync(fd)
                finally:
                    os.close(fd)
                return payload
            self.nonce = None
            raise LockBusyError(state or {}, stale) from None

    def owns(self) -> bool:
        if not self.nonce:
            return False
        state = self.read_state()
        return bool(state) and state.get("nonce") == self.nonce

    def heartbeat(self) -> bool:
        if not self.owns():
            return False
        state = self.read_state() or {}
        state["heartbeat_utc"] = _iso(_now())
        self._write_atomic(state)
        return True

    def release(self) -> bool:
        if not self.owns():
            return False
        try:
            self.path.unlink()
            return True
        except OSError:
            return False

    def state_info(self) -> dict:
        state = self.read_state()
        return {
            "locked": state is not None,
            "owned": self.owns(),
            "holder_workstation": (state or {}).get("workstation", ""),
            "holder_pid": int((state or {}).get("pid", 0) or 0),
            "acquired_utc": (state or {}).get("acquired_utc", ""),
            "heartbeat_utc": (state or {}).get("heartbeat_utc", ""),
            "stale": self.is_stale(state),
        }

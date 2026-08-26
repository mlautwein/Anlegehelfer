import json

import pytest

from lims_assistant.store import db
from lims_assistant.sync.lock import LockBusyError, SharedLock
from lims_assistant.sync.snapshot import SnapshotError, SnapshotSync


def test_lock_exklusiv_zweiter_start_scheitert(tmp_path):
    share = tmp_path / "share"
    l1 = SharedLock(share, workstation="PC-1")
    l1.acquire()
    l2 = SharedLock(share, workstation="PC-2")
    with pytest.raises(LockBusyError) as exc:
        l2.acquire()
    assert exc.value.holder["workstation"] == "PC-1"
    assert exc.value.stale is False
    assert l1.owns() and not l2.owns()
    assert l1.release()
    l2.acquire()  # nach Freigabe moeglich
    assert l2.owns()


def test_stale_lock_keine_automatische_uebernahme(tmp_path):
    share = tmp_path / "share"
    l1 = SharedLock(share, workstation="PC-1", stale_minutes=0)
    l1.acquire()
    import time

    time.sleep(0.01)
    l2 = SharedLock(share, workstation="PC-2", stale_minutes=0)
    with pytest.raises(LockBusyError) as exc:
        l2.acquire()  # stale, aber KEINE automatische Uebernahme
    assert exc.value.stale is True
    # erst mit expliziter Benutzerentscheidung:
    l2.acquire(takeover_stale=True)
    assert l2.owns()
    assert not l1.owns()  # alter Nonce passt nicht mehr


def test_heartbeat_aktualisiert_und_schuetzt(tmp_path):
    share = tmp_path / "share"
    lock = SharedLock(share, workstation="PC-1", stale_minutes=0)
    lock.acquire()
    assert lock.heartbeat()
    fremd = SharedLock(share, workstation="PC-2")
    assert not fremd.heartbeat()  # ohne Ownership kein Heartbeat
    assert not fremd.release()  # und keine Freigabe fremder Locks


def _make_db(path, marker):
    con = db.connect(path)
    with con:
        con.execute(
            "INSERT INTO meta(key, value) VALUES('marker', ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (marker,),
        )
    con.close()


def _read_marker(path):
    con = db.connect(path)
    row = con.execute("SELECT value FROM meta WHERE key='marker'").fetchone()
    con.close()
    return row["value"] if row else None


def test_push_pull_roundtrip_mit_hashpruefung(tmp_path):
    share = tmp_path / "share"
    local1 = tmp_path / "pc1" / "lims.sqlite"
    local2 = tmp_path / "pc2" / "lims.sqlite"
    _make_db(local1, "stand-1")

    s1 = SnapshotSync(share, local1)
    assert s1.push() is True
    meta = s1.read_meta()
    assert meta["sequence"] == 1 and meta["db_sha256"]

    s2 = SnapshotSync(share, local2)
    assert s2.pull() is True
    assert _read_marker(local2) == "stand-1"


def test_beschaedigter_snapshot_wird_erkannt(tmp_path):
    share = tmp_path / "share"
    local = tmp_path / "pc1" / "lims.sqlite"
    _make_db(local, "x")
    sync = SnapshotSync(share, local)
    sync.push()
    # Snapshot manipulieren
    snap = share / "data" / "snapshot.sqlite"
    snap.write_bytes(snap.read_bytes() + b"KORRUPT")
    with pytest.raises(SnapshotError, match="Hash"):
        SnapshotSync(share, tmp_path / "pc2" / "lims.sqlite").pull()


def test_pushfehler_setzt_pending_und_erhaelt_zentralen_stand(tmp_path, monkeypatch):
    share = tmp_path / "share"
    local = tmp_path / "pc1" / "lims.sqlite"
    _make_db(local, "stand-1")
    sync = SnapshotSync(share, local)
    sync.push()

    _make_db(local, "stand-2")
    import shutil

    original = shutil.copyfile
    calls = {"n": 0}

    def failing(src, dst, **kw):
        # Fehler beim Schreiben in den Share (zweiter copyfile-Aufruf im Push)
        if "share" in str(dst):
            raise OSError("Netzwerk weg (simuliert)")
        return original(src, dst, **kw)

    monkeypatch.setattr("lims_assistant.sync.snapshot.shutil.copyfile", failing)
    with pytest.raises(SnapshotError):
        sync.push()
    assert sync.has_pending()
    monkeypatch.undo()

    # Zentraler Stand ist unveraendert stand-1
    check = tmp_path / "check" / "lims.sqlite"
    SnapshotSync(share, check).pull()
    assert _read_marker(check) == "stand-1"

    # Pull ueberschreibt lokalen Pending-Stand NICHT
    assert sync.pull() is False
    assert _read_marker(local) == "stand-2"

    # Naechster Push raeumt Pending auf
    assert sync.push() is True
    assert not sync.has_pending()
    SnapshotSync(share, check).pull()
    assert _read_marker(check) == "stand-2"


def test_backups_rollierend(tmp_path):
    share = tmp_path / "share"
    local = tmp_path / "pc" / "lims.sqlite"
    sync = SnapshotSync(share, local)
    for i in range(8):
        _make_db(local, f"stand-{i}")
        import time

        time.sleep(0.01)
        sync.push()
    backups = list((share / "data" / "backups").glob("snapshot-*.sqlite"))
    assert 1 <= len(backups) <= 5

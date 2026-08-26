"""Runner-Handler: app_open/app_close, Export-mit-Bestaetigung, Health."""

import json
from pathlib import Path

from lims_assistant.contracts.models import JobRequest
from lims_assistant.jobs.runner import execute


def _open_app(settings, share, ws="PC-1", takeover=False):
    return execute(
        JobRequest(
            kind="app_open",
            payload={
                "share_dir": str(share),
                "workstation": ws,
                "takeover_stale": takeover,
            },
        ),
        settings,
    )


def test_app_open_lokalbetrieb_ohne_share(settings):
    resp = execute(JobRequest(kind="app_open", payload={"workstation": "PC"}), settings)
    assert resp.ok
    r = resp.typed_result()
    assert r.lock_acquired and not r.read_only
    assert any("lokaler Betrieb" in w for w in r.warnings)


def test_app_open_zweiter_arbeitsplatz_nur_lesend(settings, tmp_path, monkeypatch):
    share = tmp_path / "share"
    r1 = _open_app(settings, share, "PC-1")
    assert r1.ok and r1.typed_result().lock_acquired

    # Zweiter "Arbeitsplatz": eigenes lokales Datenverzeichnis
    monkeypatch.setenv("LIMS_DATA_DIR", str(tmp_path / "pc2-data"))
    r2 = _open_app(settings, share, "PC-2")
    assert r2.ok
    t2 = r2.typed_result()
    assert t2.lock_acquired is False
    assert t2.read_only is True
    assert t2.lock.holder_workstation == "PC-1"


def test_app_close_pusht_snapshot_und_gibt_lock_frei(settings, fixtures_dir, tmp_path):
    share = tmp_path / "share"
    assert _open_app(settings, share).typed_result().lock_acquired

    # etwas Arbeit erzeugen
    resp = execute(
        JobRequest(
            kind="analyze",
            payload={
                "sources": [
                    {
                        "type": "pdf",
                        "paths": [str(fixtures_dir / "seniorenresidenz_freitext.pdf")],
                    }
                ]
            },
        ),
        settings,
    )
    assert resp.ok

    close = execute(JobRequest(kind="app_close", payload={}), settings)
    assert close.ok
    t = close.typed_result()
    assert t.snapshot_pushed is True
    assert t.lock_released is True
    assert (share / "data" / "snapshot.sqlite").is_file()
    meta = json.loads((share / "data" / "snapshot.meta.json").read_text())
    assert meta["sequence"] == 1

    # danach kann ein anderer Arbeitsplatz uebernehmen und sieht die Daten
    r2 = _open_app(settings, share, "PC-2")
    assert r2.typed_result().lock_acquired
    assert r2.typed_result().snapshot_pulled is True


def test_export_job_bestaetigt_exportierte_zellen(settings, fixtures_dir, tmp_path):
    resp = execute(
        JobRequest(
            kind="analyze",
            payload={
                "sources": [
                    {"type": "pdf", "paths": [str(fixtures_dir / "klinik_digital.pdf")]}
                ]
            },
        ),
        settings,
    )
    res = resp.typed_result()
    target = tmp_path / "export"
    target.mkdir()
    rows_payload = [
        {
            "row_id": r.row_id,
            "values": {k: v.value for k, v in r.fields.items()},
        }
        for r in res.rows
    ]
    exp = execute(
        JobRequest(
            kind="export_csv",
            payload={
                "session_id": res.session_id,
                "rows": rows_payload,
                "encoding": "utf8_bom",
                "target_dir": str(target),
                "client_event_id": "exp1",
            },
        ),
        settings,
    )
    assert exp.ok, exp.error
    t = exp.typed_result()
    assert t.row_count == 14
    assert (target / "B4.csv").is_file()
    # Export bestaetigt alle exportierten Zellen -> Lernbeispiele vorhanden
    rb = execute(JobRequest(kind="rebuild_learning", payload={}), settings).typed_result()
    assert rb.examples_active > 0

    # Wiederholter Export ist idempotent (gleiche Werte -> keine neuen Beispiele)
    exp2 = execute(
        JobRequest(
            kind="export_csv",
            payload={
                "session_id": res.session_id,
                "rows": rows_payload,
                "encoding": "utf8_bom",
                "target_dir": str(target),
                "client_event_id": "exp2",
            },
        ),
        settings,
    )
    assert exp2.ok
    rb2 = execute(JobRequest(kind="rebuild_learning", payload={}), settings).typed_result()
    assert rb2.examples_active == rb.examples_active
    assert rb2.index_hash == rb.index_hash


def test_export_ohne_ziel_ist_fehler(settings):
    resp = execute(
        JobRequest(
            kind="export_csv",
            payload={"rows": [], "client_event_id": "x"},
        ),
        settings,
    )
    assert not resp.ok
    assert resp.error.code == "bad_request"


def test_health_meldet_kernzustand(settings):
    resp = execute(JobRequest(kind="health", payload={}), settings)
    assert resp.ok
    h = resp.typed_result()
    assert h.app_version and h.db_schema_version == 1
    assert h.ocr.engine in ("rapidocr", "tesseract", "none")
    assert h.llm.enabled is False


def test_unbekannte_zeile_bad_request(settings):
    resp = execute(
        JobRequest(
            kind="apply_revision",
            payload={
                "session_id": "s",
                "row_id": "fehlt",
                "field": "B4",
                "old_value": "",
                "new_value": "x",
                "client_event_id": "e",
            },
        ),
        settings,
    )
    assert not resp.ok and resp.error.code == "bad_request"

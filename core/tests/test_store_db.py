import pytest

from lims_assistant.store import db, repo


def test_migration_erzeugt_schema_v1(tmp_path):
    con = db.connect(tmp_path / "neu.sqlite")
    assert db.get_schema_version(con) == 1
    tables = {
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for expected in (
        "import_session",
        "source_document",
        "source_fragment",
        "sample_row",
        "sample_field",
        "field_proposal",
        "revision_event",
        "row_event",
        "confirmation_event",
        "learning_example",
        "model_version",
        "model_update_event",
        "export_event",
        "data_snapshot",
        "event_log",
    ):
        assert expected in tables
    assert db.integrity_ok(con)
    con.close()


def test_migration_idempotent(tmp_path):
    p = tmp_path / "x.sqlite"
    db.connect(p).close()
    con = db.connect(p)  # zweiter Connect migriert nicht erneut
    assert db.get_schema_version(con) == 1
    con.close()


def test_zukunftsversion_wird_abgelehnt(tmp_path):
    p = tmp_path / "future.sqlite"
    con = db.connect(p)
    con.execute("UPDATE meta SET value='99' WHERE key='schema_version'")
    con.commit()
    con.close()
    with pytest.raises(RuntimeError, match="neuer"):
        db.connect(p)


def test_row_mit_genau_fuenf_feldern(tmp_path):
    con = db.connect(tmp_path / "rows.sqlite")
    with con:
        sid = repo.create_session(con)
        rid = repo.add_row(con, sid, source_order=1)
    fields = repo.get_fields(con, rid)
    assert sorted(fields) == ["B3", "B4", "Bez1", "Bez2", "Untersuchungsart"]
    con.close()


def test_confirmation_dedupe(tmp_path):
    con = db.connect(tmp_path / "conf.sqlite")
    with con:
        sid = repo.create_session(con)
        rid = repo.add_row(con, sid, source_order=1)
        e1, c1 = repo.add_confirmation(
            con,
            session_id=sid,
            confirmation_type="export",
            row_id=rid,
            field_name="B4",
            value="Warmwasser",
            client_event_id="a",
        )
        e2, c2 = repo.add_confirmation(
            con,
            session_id=sid,
            confirmation_type="copy_column",  # anderer Typ, gleiche Zelle+Wert
            row_id=rid,
            field_name="B4",
            value="Warmwasser",
            client_event_id="b",
        )
    assert c1 is True and c2 is False and e1 == e2
    con.close()

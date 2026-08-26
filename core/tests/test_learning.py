"""Lernmechanik: Korrektur, Bestaetigung, Idempotenz, Undo, Rebuild, Retrieval."""

from lims_assistant.contracts.models import JobRequest
from lims_assistant.jobs.runner import execute


def _analyze(settings, fixtures_dir, name="klinik_digital.pdf", session=None):
    req = JobRequest(
        kind="analyze",
        payload={
            "session_id": session,
            "sources": [{"type": "pdf", "paths": [str(fixtures_dir / name)]}],
        },
    )
    resp = execute(req, settings)
    assert resp.ok, resp.error
    return resp.typed_result()


def _revise(settings, session_id, row_id, field, old, new, ce="ce1"):
    resp = execute(
        JobRequest(
            kind="apply_revision",
            payload={
                "session_id": session_id,
                "row_id": row_id,
                "field": field,
                "old_value": old,
                "new_value": new,
                "client_event_id": ce,
            },
        ),
        settings,
    )
    assert resp.ok, resp.error
    return resp.typed_result()


def _rebuild(settings):
    resp = execute(JobRequest(kind="rebuild_learning", payload={}), settings)
    assert resp.ok
    return resp.typed_result()


def test_zellkorrektur_lernt_und_beeinflusst_folgefall(settings, fixtures_dir):
    """MVP-Kriterium 3: Korrektur -> aehnlicher Folgefall nutzt den Lernstand."""
    res1 = _analyze(settings, fixtures_dir)
    row = res1.rows[0]  # Zimmer 530, Patientenzimmer, Kaltwasser
    assert row.fields["Untersuchungsart"].value == "Legionellen"
    _revise(
        settings,
        res1.session_id,
        row.row_id,
        "Untersuchungsart",
        "Legionellen",
        "Legionellen (TrinkwV)",
    )
    st = _rebuild(settings)
    assert st.examples_active == 1

    # Gleiches Dokument erneut (aehnlichste Zeile = dieselbe): Retrieval schlaegt
    # den gelernten Wert vor - als abgeleiteter Wert gelb markiert.
    res2 = _analyze(settings, fixtures_dir)
    row2 = res2.rows[0]
    assert row2.fields["Untersuchungsart"].value == "Legionellen (TrinkwV)"
    assert row2.fields["Untersuchungsart"].is_uncertain is True
    # Andere Felder unveraendert sicher
    assert row2.fields["B4"].value == "Kaltwasser"


def test_revision_ist_idempotent_je_client_event(settings, fixtures_dir):
    res = _analyze(settings, fixtures_dir)
    row = res.rows[0]
    r1 = _revise(settings, res.session_id, row.row_id, "B4", "Kaltwasser", "Warmwasser", ce="dup")
    r2 = _revise(settings, res.session_id, row.row_id, "B4", "Kaltwasser", "Warmwasser", ce="dup")
    assert r1.event_id == r2.event_id
    assert r1.learned is True and r2.learned is False
    assert _rebuild(settings).examples_active == 1


def test_bestaetigung_idempotent_ohne_mehrfachgewicht(settings, fixtures_dir):
    res = _analyze(settings, fixtures_dir)
    row = res.rows[0]
    payload = {
        "session_id": res.session_id,
        "confirmation_type": "copy_column",
        "cells": [
            {"row_id": row.row_id, "field": "B4", "value": row.fields["B4"].value}
        ],
        "client_event_id": "c1",
    }
    resp1 = execute(JobRequest(kind="confirm_cells", payload=payload), settings)
    stats1 = _rebuild(settings)
    payload["client_event_id"] = "c2"
    payload["confirmation_type"] = "copy_selection"
    resp2 = execute(JobRequest(kind="confirm_cells", payload=payload), settings)
    stats2 = _rebuild(settings)
    assert resp1.typed_result().new_examples == 1
    assert resp2.typed_result().duplicates == 1
    assert stats1.examples_active == stats2.examples_active == 1
    assert stats1.index_hash == stats2.index_hash


def test_geloeschte_auto_zeile_ist_negatives_beispiel(settings, fixtures_dir):
    res = _analyze(settings, fixtures_dir)
    row = res.rows[3]
    resp = execute(
        JobRequest(
            kind="row_event",
            payload={
                "session_id": res.session_id,
                "row_id": row.row_id,
                "action": "delete",
                "client_event_id": "d1",
            },
        ),
        settings,
    )
    assert resp.ok
    stats = _rebuild(settings)
    assert stats.row_examples_active == 1


def test_manuelle_zeile_wird_erst_nach_bestaetigung_positiv(settings, fixtures_dir):
    res = _analyze(settings, fixtures_dir)
    add = execute(
        JobRequest(
            kind="row_event",
            payload={
                "session_id": res.session_id,
                "row_id": "11111111-1111-1111-1111-111111111111",
                "action": "add",
                "values": {
                    "Bez1": "Haus C",
                    "Bez2": "EG, Zimmer 1",
                    "B3": "Waschbecken, Einhandmischarmatur",
                    "B4": "Kaltwasser",
                    "Untersuchungsart": "Legionellen",
                },
                "client_event_id": "a1",
            },
        ),
        settings,
    )
    assert add.ok
    assert _rebuild(settings).row_examples_active == 0  # noch kein Positivbeispiel

    conf = execute(
        JobRequest(
            kind="confirm_cells",
            payload={
                "session_id": res.session_id,
                "confirmation_type": "export",
                "cells": [
                    {
                        "row_id": "11111111-1111-1111-1111-111111111111",
                        "field": "B4",
                        "value": "Kaltwasser",
                    }
                ],
                "client_event_id": "a2",
            },
        ),
        settings,
    )
    assert conf.ok
    stats = _rebuild(settings)
    assert stats.row_examples_active == 1  # jetzt positives Zeilenbeispiel


def test_undo_kompensiert_revision_und_rebuild_ist_deterministisch(settings, fixtures_dir):
    res = _analyze(settings, fixtures_dir)
    row = res.rows[0]
    _revise(settings, res.session_id, row.row_id, "B3", row.fields["B3"].value, "Falscher Wert", ce="u1")
    before = _rebuild(settings)
    assert before.examples_active == 1

    undo = execute(
        JobRequest(
            kind="undo",
            payload={"session_id": res.session_id, "client_event_id": "u2"},
        ),
        settings,
    )
    assert undo.ok
    tr = undo.typed_result()
    assert tr.compensated_kind == "revision"
    after = _rebuild(settings)
    assert after.examples_active == 0
    assert after.index_hash != before.index_hash

    # Wiederholte identische Korrektur reaktiviert dasselbe Beispiel (kein Duplikat)
    _revise(settings, res.session_id, row.row_id, "B3", row.fields["B3"].value, "Falscher Wert", ce="u3")
    again = _rebuild(settings)
    assert again.examples_active == 1
    assert again.index_hash == before.index_hash  # gleicher aktiver Verlauf -> gleicher Hash


def test_undo_add_und_delete_zeile(settings, fixtures_dir):
    res = _analyze(settings, fixtures_dir)
    row = res.rows[2]
    execute(
        JobRequest(
            kind="row_event",
            payload={
                "session_id": res.session_id,
                "row_id": row.row_id,
                "action": "delete",
                "client_event_id": "del1",
            },
        ),
        settings,
    )
    assert _rebuild(settings).row_examples_active == 1
    undo = execute(
        JobRequest(kind="undo", payload={"session_id": res.session_id, "client_event_id": "del2"}),
        settings,
    )
    assert undo.typed_result().compensated_kind == "row_delete"
    assert _rebuild(settings).row_examples_active == 0  # Negativbeispiel deaktiviert


def test_zeilendetektor_braucht_mindestbeispiele(db_con):
    from lims_assistant.learn.rowclf import RowClassifier

    clf = RowClassifier()
    clf.build([("eg kueche spuele ehm kw", "1")])
    assert clf.probability("eg bad wt ehm") is None  # zu wenig Beispiele
    items = [
        ("eg kueche spuele ehm kaltwasser", "1"),
        ("1 og bad waschbecken ehm warmwasser", "1"),
        ("ug technikraum zirkulation pnv", "1"),
        ("seite 2 von 3", "0"),
        ("erstellt am 24.08.2026", "0"),
        ("mit freundlichen gruessen", "0"),
    ]
    clf.build(items)
    assert clf.ready()
    assert clf.probability("2 og bad waschbecken ehm kaltwasser") > 0.5
    assert clf.probability("seite 3 von 3") < 0.5


def test_retrieval_top_k_deterministisch():
    from lims_assistant.learn.index import TfIdfIndex

    idx = TfIdfIndex()
    idx.build(
        [
            ("a", "eg kueche spuele ehm kaltwasser", "Kaltwasser"),
            ("b", "ug technikraum zirkulation pnv", "Warmwasser, Zirkulation"),
            ("c", "1 og bad waschbecken ehm warmwasser", "Warmwasser"),
        ]
    )
    hits = idx.query("eg kueche spuele einhandmischer kaltwasser", top_k=2)
    assert hits[0][0] == "a" and hits[0][2] > 0.5
    h1 = idx.content_hash()
    idx.build(
        [
            ("a", "eg kueche spuele ehm kaltwasser", "Kaltwasser"),
            ("b", "ug technikraum zirkulation pnv", "Warmwasser, Zirkulation"),
            ("c", "1 og bad waschbecken ehm warmwasser", "Warmwasser"),
        ]
    )
    assert idx.content_hash() == h1

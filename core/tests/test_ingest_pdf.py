import json

from lims_assistant.domain.entities import FIELDS


def gold(fixtures_dir, name):
    data = json.loads(
        (fixtures_dir / "gold" / "expected.json").read_text(encoding="utf-8")
    )
    return data[name]


def test_digitale_tabellen_pdf_end_to_end(run_pdf, fixtures_dir):
    res = run_pdf("klinik_digital.pdf")
    expected = gold(fixtures_dir, "klinik_digital.pdf")
    assert len(res.rows) == len(expected) == 14
    for row, exp in zip(res.rows, expected):
        for fname in FIELDS:
            assert row.fields[fname].value == exp[fname], (
                f"Zeile {row.source_order} Feld {fname}"
            )
        for fname, must_be_uncertain in exp.get("uncertain", {}).items():
            assert row.fields[fname].is_uncertain == must_be_uncertain


def test_mehrere_objekte_zeilenbezogen(run_pdf):
    res = run_pdf("klinik_digital.pdf")
    bez1 = [r.fields["Bez1"].value for r in res.rows]
    assert bez1[0].endswith("Haus A") and bez1[-1].endswith("Haus B")
    assert len(set(bez1)) == 2
    # Objektkontext aus expliziter Ueberschrift ist nicht gelb
    assert not res.rows[0].fields["Bez1"].is_uncertain


def test_duplikate_bleiben_erhalten(run_pdf):
    res = run_pdf("klinik_digital.pdf")
    keys = [
        tuple(r.fields[f].value for f in FIELDS) for r in res.rows
    ]
    assert len(keys) != len(set(keys)), "bewusstes Duplikat wurde entfernt"


def test_prompt_injection_wird_nicht_uebernommen(run_pdf, db_con):
    res = run_pdf("klinik_digital.pdf")
    for row in res.rows:
        for fname in FIELDS:
            assert "FREIGEGEBEN" not in row.fields[fname].value
    # Injection-Zeile liegt als verworfenes Fragment vor, nicht als Probenzeile
    frags = db_con.execute(
        "SELECT kind, text FROM source_fragment WHERE text LIKE '%FREIGEGEBEN%'"
    ).fetchall()
    assert frags and all(f["kind"] == "line" for f in frags)


def test_quellreihenfolge_stabil(run_pdf):
    res = run_pdf("klinik_digital.pdf")
    orders = [r.source_order for r in res.rows]
    assert orders == sorted(orders) == list(range(1, len(orders) + 1))


def test_freitext_pdf(run_pdf, fixtures_dir):
    res = run_pdf("seniorenresidenz_freitext.pdf")
    expected = gold(fixtures_dir, "seniorenresidenz_freitext.pdf")
    assert len(res.rows) == len(expected) == 5
    for row, exp in zip(res.rows, expected):
        for fname in FIELDS:
            assert row.fields[fname].value == exp[fname]
    # Hinweiszeile ("Zutritt nur mit Begleitung") ist keine Probenstelle
    assert all("Zutritt" not in r.fields["B3"].value for r in res.rows)


def test_leeres_ergebnis_liefert_konkrete_warnung(db_con, settings, tmp_path):
    from reportlab.pdfgen import canvas

    from lims_assistant.contracts.models import AnalyzePayload, AnalyzeSource
    from lims_assistant.pipeline.analyze import run_analyze

    p = tmp_path / "leer.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(100, 700, "Allgemeines Anschreiben ohne Probenliste")
    c.save()
    res = run_analyze(
        db_con,
        settings,
        AnalyzePayload(sources=[AnalyzeSource(type="pdf", paths=[str(p)])]),
    )
    assert res.rows == []
    assert any("Keine Probenstellen erkannt" in w for w in res.warnings)


def test_mehrere_importe_haengen_an(db_con, settings, fixtures_dir):
    from lims_assistant.contracts.models import AnalyzePayload, AnalyzeSource
    from lims_assistant.pipeline.analyze import run_analyze

    first = run_analyze(
        db_con,
        settings,
        AnalyzePayload(
            sources=[
                AnalyzeSource(
                    type="pdf", paths=[str(fixtures_dir / "klinik_digital.pdf")]
                )
            ]
        ),
    )
    second = run_analyze(
        db_con,
        settings,
        AnalyzePayload(
            session_id=first.session_id,
            sources=[
                AnalyzeSource(
                    type="pdf",
                    paths=[str(fixtures_dir / "seniorenresidenz_freitext.pdf")],
                )
            ],
        ),
    )
    assert second.session_id == first.session_id
    assert second.rows[0].source_order == len(first.rows) + 1
    # Exportziel bleibt der Ordner der ZUERST importierten Datei
    assert second.export_base_dir == str(fixtures_dir.resolve())


def test_seitenauswahl(db_con, settings, fixtures_dir):
    from lims_assistant.contracts.models import AnalyzePayload, AnalyzeSource
    from lims_assistant.pipeline.analyze import run_analyze

    res = run_analyze(
        db_con,
        settings,
        AnalyzePayload(
            sources=[
                AnalyzeSource(
                    type="pdf",
                    paths=[str(fixtures_dir / "klinik_digital.pdf")],
                    pages=[2],
                )
            ]
        ),
    )
    assert len(res.rows) == 5  # nur Haus B
    assert all(r.fields["Bez1"].value.endswith("Haus B") for r in res.rows)

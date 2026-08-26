import pytest

from lims_assistant.contracts.models import AnalyzePayload, AnalyzeSource
from lims_assistant.ingest.excel_ingest import has_macros, ingest_excel, list_sheets
from lims_assistant.pipeline.analyze import run_analyze


def test_list_sheets_xlsx(fixtures_dir):
    sheets, macros, warnings = list_sheets(fixtures_dir / "wohnhaus.xlsx")
    names = [s.name for s in sheets]
    assert names == ["Wohnhaus Gartenstr. 12", "Anlagenliste", "Kita Sonnenblume"]
    assert macros is False
    assert all(s.visible for s in sheets)


def test_xlsm_wird_gelesen_aber_makros_nie_ausgefuehrt(fixtures_dir):
    path = fixtures_dir / "wohnhaus_makro.xlsm"
    assert has_macros(path) is True
    sheets, macros, warnings = list_sheets(path)
    assert macros is True
    assert any("nicht ausgefuehrt" in w for w in warnings)
    doc = ingest_excel(path, sheets=["Wohnhaus Gartenstr. 12"])
    assert any("Makros" in w for w in doc.warnings)
    assert len(doc.segment.rows) == 6
    # identische Daten wie die makrofreie XLSX -> reiner Datenimport
    doc_plain = ingest_excel(
        fixtures_dir / "wohnhaus.xlsx", sheets=["Wohnhaus Gartenstr. 12"]
    )
    assert [r.source_text for r in doc.segment.rows] == [
        r.source_text for r in doc_plain.segment.rows
    ]


def test_blattauswahl_nur_gewaehlte_blaetter(db_con, settings, fixtures_dir):
    res = run_analyze(
        db_con,
        settings,
        AnalyzePayload(
            sources=[
                AnalyzeSource(
                    type="excel",
                    paths=[str(fixtures_dir / "wohnhaus.xlsx")],
                    sheets=["Kita Sonnenblume"],
                )
            ]
        ),
    )
    assert len(res.rows) == 2
    assert all(
        r.fields["Bez1"].value == "Kita Sonnenblume" for r in res.rows
    )
    # Blattname als Objektkontext ist nur abgeleitet -> gelb
    assert all(r.fields["Bez1"].is_uncertain for r in res.rows)


def test_mehrblatt_ohne_auswahl_ist_fehler(db_con, settings, fixtures_dir):
    with pytest.raises(ValueError, match="Blattauswahl"):
        run_analyze(
            db_con,
            settings,
            AnalyzePayload(
                sources=[
                    AnalyzeSource(
                        type="excel", paths=[str(fixtures_dir / "wohnhaus.xlsx")]
                    )
                ]
            ),
        )


def test_xls_altformat(db_con, settings, fixtures_dir):
    res = run_analyze(
        db_con,
        settings,
        AnalyzePayload(
            sources=[
                AnalyzeSource(
                    type="excel",
                    paths=[str(fixtures_dir / "altbestand.xls")],
                    sheets=["Altbestand"],
                )
            ]
        ),
    )
    assert len(res.rows) == 2
    assert res.rows[0].fields["B3"].value == "Trinkbrunnen"
    assert res.rows[1].fields["Bez2"].value == "DG, Zimmer 7, Bewohnerzimmer"


def test_wohnhaus_werte(db_con, settings, fixtures_dir):
    res = run_analyze(
        db_con,
        settings,
        AnalyzePayload(
            sources=[
                AnalyzeSource(
                    type="excel",
                    paths=[str(fixtures_dir / "wohnhaus.xlsx")],
                    sheets=["Wohnhaus Gartenstr. 12"],
                )
            ]
        ),
    )
    b4 = [r.fields["B4"].value for r in res.rows]
    assert b4 == [
        "Kaltwasser",
        "Warmwasser",
        "Warmwasser",
        "Warmwasser",
        "Kaltwasser",
        "Warmwasser, Speicher",
    ]
    assert res.rows[4].fields["B3"].value == "Ausgussbecken, Standventil"
    assert res.rows[5].fields["B3"].value == "Rücklauf, PNV"

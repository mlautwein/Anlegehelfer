from lims_assistant.pipeline.zusatz import hint_fields


def test_hint_untersuchungsart_und_medium():
    h = hint_fields("Bitte alles nur Kaltwasser, Untersuchung auf Legionellen")
    assert h["Untersuchungsart"] == "Legionellen"
    assert h["B4"] == "Kaltwasser"


def test_hint_objektname():
    h = hint_fields("Klinikum Sonnental, zweiter Durchgang")
    assert h["Bez1"] == "Klinikum Sonnental"


def test_hint_haus_pattern():
    h = hint_fields("Es geht um Haus C, wie letztes Mal")
    assert h["Bez1"] == "Haus C"


def test_hint_widerspruechliches_medium_ergibt_nichts():
    h = hint_fields("Kaltwasser und Warmwasser beproben")
    assert "B4" not in h


def test_hint_leer():
    assert hint_fields("") == {}
    assert hint_fields("   ") == {}


def test_hint_fuellt_nur_leere_felder_und_ist_gelb(db_con, settings, tmp_path):
    from reportlab.pdfgen import canvas

    from lims_assistant.contracts.models import AnalyzePayload, AnalyzeSource
    from lims_assistant.pipeline.analyze import run_analyze

    p = tmp_path / "mini.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(80, 700, "Zi. 12, 1. OG, Bad Waschbecken EHM, KW")
    c.save()
    res = run_analyze(
        db_con,
        settings,
        AnalyzePayload(
            sources=[AnalyzeSource(type="pdf", paths=[str(p)])],
            hint_text="Pflegeheim Talblick, bitte Legionellen",
        ),
    )
    assert len(res.rows) == 1
    row = res.rows[0]
    # Zusatztext fuellt leere Felder ...
    assert row.fields["Bez1"].value == "Pflegeheim Talblick"
    assert row.fields["Untersuchungsart"].value == "Legionellen"
    # ... und ist IMMER gelb markiert
    assert row.fields["Bez1"].is_uncertain
    assert row.fields["Untersuchungsart"].is_uncertain
    # direkte Werte bleiben unberuehrt und nicht gelb
    assert row.fields["B4"].value == "Kaltwasser"
    assert not row.fields["B4"].is_uncertain

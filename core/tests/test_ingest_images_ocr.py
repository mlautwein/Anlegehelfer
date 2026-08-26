"""OCR-/Bildtests mit echten lokalen Engines (RapidOCR bzw. Tesseract).

Diese Tests laufen gegen echte OCR-Komponenten (kein Mock) und werden
uebersprungen, wenn im Testsystem keine Engine verfuegbar ist.
"""

import pytest

from lims_assistant.config import Settings
from lims_assistant.contracts.models import AnalyzePayload, AnalyzeSource
from lims_assistant.ocr.base import get_engine
from lims_assistant.pipeline.analyze import run_analyze


def _engine():
    return get_engine(Settings().ocr)


requires_ocr = pytest.mark.skipif(
    _engine() is None, reason="keine OCR-Engine im Testsystem verfuegbar"
)


@requires_ocr
def test_scan_pdf_ohne_textschicht_laeuft_ueber_ocr(db_con, settings, fixtures_dir):
    res = run_analyze(
        db_con,
        settings,
        AnalyzePayload(
            sources=[
                AnalyzeSource(type="pdf", paths=[str(fixtures_dir / "schule_scan.pdf")])
            ]
        ),
    )
    assert res.stats.ocr_pages >= 1
    assert len(res.rows) >= 4
    texts = " | ".join(
        r.fields["B3"].value + " " + r.fields["B4"].value for r in res.rows
    )
    assert "Waschbecken" in texts
    assert "Kaltwasser" in texts or "Warmwasser" in texts


@requires_ocr
def test_bildgruppe_png_und_jpg_in_reihenfolge(db_con, settings, fixtures_dir):
    res = run_analyze(
        db_con,
        settings,
        AnalyzePayload(
            sources=[
                AnalyzeSource(
                    type="image_set",
                    paths=[
                        str(fixtures_dir / "schule_scan_sauber.png"),
                        str(fixtures_dir / "schule_foto_verrauscht.jpg"),
                    ],
                )
            ]
        ),
    )
    assert res.stats.ocr_pages == 2
    assert len(res.rows) >= 4
    # Bez1-Kontext aus 'Objekt:'-Kopf des Scans
    assert any("Grundschule" in r.fields["Bez1"].value for r in res.rows)


@requires_ocr
def test_heic_dekodierung(db_con, settings, fixtures_dir):
    heic = fixtures_dir / "schule_foto.heic"
    if not heic.exists():
        pytest.skip("HEIC-Fixture nicht vorhanden")
    res = run_analyze(
        db_con,
        settings,
        AnalyzePayload(
            sources=[AnalyzeSource(type="image_set", paths=[str(heic)])]
        ),
    )
    assert res.stats.ocr_pages == 1
    assert len(res.rows) >= 3


@requires_ocr
def test_umlaute_in_ocr_ergebnis(db_con, settings, fixtures_dir):
    """Teekueche muss als Teekueche/Teeküche erkannt werden (ggf. via Fuzzy)."""
    res = run_analyze(
        db_con,
        settings,
        AnalyzePayload(
            sources=[
                AnalyzeSource(
                    type="image_set",
                    paths=[str(fixtures_dir / "schule_scan_sauber.png")],
                )
            ]
        ),
    )
    bez2 = " | ".join(r.fields["Bez2"].value for r in res.rows)
    assert "Teeküche" in bez2


def _rapidocr_installiert() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(
    not _rapidocr_installiert(), reason="rapidocr-onnxruntime nicht installiert"
)
def test_fehlendes_zusatzmodell_faellt_auf_standardmodelle_zurueck():
    """Ein konfiguriertes, aber nicht provisioniertes Modell darf OCR nicht abschalten.

    Die ausgelieferte config.json zeigt auf das Latin-Rec-Modell, das erst
    per provision_offline.ps1 daneben gelegt wird. Vorher wirft RapidOCR
    beim Laden. Da im Windows-Paket kein Tesseract liegt, blieb frueher gar
    keine Engine uebrig und Scans lieferten kommentarlos null Zeilen.
    """
    from lims_assistant.config import OcrConfig
    from lims_assistant.ocr.base import engine_health

    cfg = OcrConfig(
        engine="rapidocr",
        rec_model_path="core/models/ocr/gibt-es-nicht.onnx",
        dict_path="core/models/ocr/gibt-es-nicht.txt",
    )
    name, ok, detail = engine_health(cfg)
    assert ok, f"OCR faellt komplett aus statt zurueck: {detail}"
    assert name == "rapidocr"
    assert "Standardmodelle" in detail


def test_engine_none_bleibt_abgeschaltet():
    """engine='none' ist eine bewusste Entscheidung und darf nicht umgangen werden."""
    from lims_assistant.config import OcrConfig
    from lims_assistant.ocr.base import engine_health

    name, ok, _ = engine_health(OcrConfig(engine="none"))
    assert (name, ok) == ("none", False)

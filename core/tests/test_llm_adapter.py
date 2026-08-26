import pytest
from pydantic import ValidationError

from lims_assistant.llm.base import LlmRowTask, sanitize_suggestion
from lims_assistant.llm.fake import FakeLlm
from lims_assistant.llm.schema import LLM_ROWS_JSON_SCHEMA, LlmRowsOut


def test_schema_verbietet_fremdfelder():
    with pytest.raises(ValidationError):
        LlmRowsOut.model_validate({"rows": [{"row_ref": 0, "Hack": "x"}]})
    with pytest.raises(ValidationError):
        LlmRowsOut.model_validate({"rows": [], "extra": 1})
    ok = LlmRowsOut.model_validate({"rows": [{"row_ref": 1, "B4": "Warmwasser"}]})
    assert ok.rows[0].field_map()["B4"] == "Warmwasser"
    assert LLM_ROWS_JSON_SCHEMA["additionalProperties"] is False


def test_sanitize_begrenzt_und_bereinigt():
    out = sanitize_suggestion(
        {
            "B4": "  Warmwasser,\r\nSpeicher  ",
            "B3": "x" * 500,
            "Boese": "ignorieren",
            "Bez2": "",
        }
    )
    assert out["B4"] == "Warmwasser, Speicher"
    assert len(out["B3"]) <= 80
    assert "Boese" not in out
    assert "Bez2" not in out  # leere Werte fallen weg


def test_fake_llm_fuellt_nur_missing_fields():
    fake = FakeLlm({"Zeile-A": {"B4": "Warmwasser", "B3": "Sollte nicht erscheinen"}})
    tasks = [
        LlmRowTask(row_ref=0, source_text="Zeile-A ohne Medium", missing_fields=["B4"]),
        LlmRowTask(row_ref=1, source_text="Zeile-B", missing_fields=["B4"]),
    ]
    out = fake.suggest(tasks)
    assert len(out) == 1
    assert out[0].row_ref == 0
    assert out[0].fields == {"B4": "Warmwasser"}


def test_pipeline_nutzt_llm_nur_fuer_luecken_und_markiert_gelb(
    db_con, settings, tmp_path
):
    from reportlab.pdfgen import canvas

    from lims_assistant.contracts.models import AnalyzePayload, AnalyzeSource
    from lims_assistant.pipeline.analyze import run_analyze

    p = tmp_path / "luecke.pdf"
    c = canvas.Canvas(str(p))
    # Zeile mit Raum, aber ohne erkennbares Medium
    c.drawString(80, 700, "Zi. 44, 2. OG, Bad Waschbecken EHM")
    c.save()

    fake = FakeLlm({"Zi. 44": {"B4": "Warmwasser"}})
    res = run_analyze(
        db_con,
        settings,
        AnalyzePayload(sources=[AnalyzeSource(type="pdf", paths=[str(p)])]),
        llm_adapter=fake,
    )
    assert len(res.rows) == 1
    row = res.rows[0]
    assert row.fields["B4"].value == "Warmwasser"
    assert row.fields["B4"].is_uncertain is True  # LLM-Ableitung immer gelb
    assert row.fields["B3"].is_uncertain is False  # direkter Wert unberuehrt
    assert res.stats.llm_rows == 1
    # LLM bekam nur die Lueckenfelder
    assert fake.calls and all(
        "B3" not in t.missing_fields for t in fake.calls[0]
    )


def test_llama_adapter_meldet_fehlende_artefakte(settings):
    from lims_assistant.config import LlmConfig
    from lims_assistant.llm.llama_server import LlamaServerAdapter

    adapter = LlamaServerAdapter(LlmConfig(enabled=True, model_path="/fehlt.gguf"))
    ok, detail = adapter.available()
    assert not ok and "fehlt" in detail

    adapter2 = LlamaServerAdapter(LlmConfig(enabled=False))
    ok2, detail2 = adapter2.available()
    assert not ok2 and "deaktiviert" in detail2

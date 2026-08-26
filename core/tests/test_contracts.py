import pytest
from pydantic import ValidationError

from lims_assistant.contracts.models import (
    AnalyzePayload,
    AnalyzeResult,
    FieldValue,
    JobRequest,
    JobResponse,
    ResultRow,
    RowValues,
    make_response,
)


def _five(**overrides):
    base = {
        "Bez1": {"value": "", "is_uncertain": False},
        "Bez2": {"value": "", "is_uncertain": False},
        "B3": {"value": "", "is_uncertain": False},
        "B4": {"value": "", "is_uncertain": False},
        "Untersuchungsart": {"value": "", "is_uncertain": False},
    }
    base.update(overrides)
    return base


def test_result_row_erzwingt_genau_fuenf_felder():
    ResultRow(row_id="r1", source_order=1, fields=_five())
    with pytest.raises(ValidationError):
        ResultRow(row_id="r1", source_order=1, fields={"Bez1": {"value": "x"}})
    with pytest.raises(ValidationError):
        bad = _five()
        bad["Extra"] = {"value": "x"}
        ResultRow(row_id="r1", source_order=1, fields=bad)


def test_leere_zeichenfolge_ist_gueltiger_positionshaltender_wert():
    row = ResultRow(row_id="r", source_order=1, fields=_five())
    assert row.fields["B4"].value == ""


def test_fieldvalue_normalisiert_umbrueche_und_tabs():
    fv = FieldValue(value="Warmwasser,\r\n\tSpeicher")
    assert fv.value == "Warmwasser, Speicher"


def test_unbekannte_felder_werden_abgelehnt():
    with pytest.raises(ValidationError):
        AnalyzePayload(sources=[], unbekannt=1)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        JobRequest(kind="analyze", payload={}, extra_feld=True)  # type: ignore[call-arg]


def test_schema_version_inkompatibel_wird_abgelehnt():
    with pytest.raises(ValidationError):
        JobRequest(schema_version="2.0", kind="health", payload={})
    JobRequest(schema_version="1.1", kind="health", payload={})  # kompatibel (Major 1)


def test_typed_payload_dispatch_und_response_roundtrip():
    req = JobRequest(
        kind="analyze",
        payload={"sources": [{"type": "pdf", "paths": ["/tmp/x.pdf"]}]},
    )
    typed = req.typed_payload()
    assert isinstance(typed, AnalyzePayload)
    assert typed.sources[0].paths == ["/tmp/x.pdf"]

    result = AnalyzeResult(session_id="s1")
    resp = make_response(req, result=result)
    raw = resp.model_dump(mode="json")
    parsed = JobResponse.model_validate(raw)
    typed_result = parsed.typed_result()
    assert isinstance(typed_result, AnalyzeResult)
    assert typed_result.session_id == "s1"


def test_row_values_as_list_reihenfolge():
    rv = RowValues(Bez1="a", Bez2="b", B3="c", B4="d", Untersuchungsart="e")
    assert rv.as_list() == ["a", "b", "c", "d", "e"]


def test_analyze_source_validierung():
    with pytest.raises(ValidationError):
        AnalyzePayload(sources=[{"type": "pdf", "paths": [" "]}])
    with pytest.raises(ValidationError):
        AnalyzePayload(sources=[{"type": "sonstiges", "paths": ["x"]}])


def test_schema_export_ist_aktuell(tmp_path):
    """contracts/schemas/ muss dem Code entsprechen (kein stiller Drift)."""
    from pathlib import Path

    from lims_assistant.contracts.export_schemas import export_all

    repo_dir = Path(__file__).resolve().parents[2] / "contracts" / "schemas"
    generated = tmp_path / "schemas"
    export_all(generated)
    gen_files = sorted(p.name for p in generated.glob("*.schema.json"))
    assert gen_files, "Schema-Export leer"
    repo_files = sorted(p.name for p in repo_dir.glob("*.schema.json"))
    assert repo_files == gen_files, "Schema-Dateien fehlen/ueberzaehlig - export-schemas ausfuehren"
    for name in gen_files:
        assert (repo_dir / name).read_text(encoding="utf-8") == (
            generated / name
        ).read_text(encoding="utf-8"), f"Schema veraltet: {name}"

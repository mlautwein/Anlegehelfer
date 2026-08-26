from lims_assistant.extract.features import CellMap, extract_features
from lims_assistant.normalize.compose import compose_all


def values(text, cells=None):
    c = compose_all(extract_features(text, cells))
    return {k: v.value for k, v in c.items()}


def scores(text, cells=None):
    c = compose_all(extract_features(text, cells))
    return {k: v.score for k, v in c.items()}


def test_sanitaere_zeile_kanonisch():
    v = values("Zi. 530, 5.OG, Bad WT EHM, WW, Legionellen")
    assert v["Bez2"] == "5. OG, Zimmer 530"
    assert v["B3"] == "Bad, Waschbecken, Einhandmischarmatur"
    assert v["B4"] == "Warmwasser"
    assert v["Untersuchungsart"] == "Legionellen"


def test_technische_zeile_erhaelt_pnv():
    v = values("Technikraum UG, Speicher Vorlauf, PNV, TWW")
    assert v["Bez2"] == "UG, Technikraum"
    assert v["B3"] == "Vorlauf, PNV"
    assert v["B4"] == "Warmwasser, Speicher"


def test_ruecklauf_konvention_zirkulation():
    v = values("Zirkulation RL PNV")
    assert v["B3"] == "Rücklauf, PNV"
    assert v["B4"] == "Warmwasser, Zirkulation"


def test_dle_technisch():
    v = values("Technikraum KG DLE Ausgang Zapfhahn WW")
    assert v["B3"] == "DLE, Zapfstelle"
    assert v["B4"] == "Warmwasser, DLE"


def test_kaltwasser_ohne_zusatz():
    v = values("EG Flur Trinkbrunnen KW")
    assert v["B4"] == "Kaltwasser"


def test_keine_haengenden_kommas_bei_fehlenden_teilen():
    v = values("Waschbecken EHM")
    assert v["B3"] == "Waschbecken, Einhandmischarmatur"
    assert v["Bez2"] == ""
    for value in v.values():
        assert not value.startswith(",")
        assert not value.endswith(",")
        assert ", ," not in value


def test_ocr_fuzzy_reparatur_wird_unsicher():
    s = scores("Patientenzlmmer 530 5. OG Waschbekcen EHM WW")
    v = values("Patientenzlmmer 530 5. OG Waschbekcen EHM WW")
    assert v["Bez2"] == "5. OG, Zimmer 530, Patientenzimmer"
    assert v["B3"] == "Waschbecken, Einhandmischarmatur"
    assert s["Bez2"] < 0.75  # fuzzy => unter Schwellwert => gelb
    assert s["B3"] < 0.75


def test_kein_ort_raumtyp_duplikat_bei_strukturzeile():
    cells = CellMap(etage="2. OG", raum="218", raumtyp="Teekueche", entnahme="Spuele, EHM", medium="WW")
    v = values("2. OG | 218 | Teekueche | Spuele, EHM | WW", cells)
    assert v["Bez2"] == "2. OG, Raum 218, Teeküche"
    assert v["B3"] == "Spüle, Einhandmischarmatur"


def test_bad_dominiert_als_ort_in_freitext():
    v = values("Zi. 12 Bad Waschbecken EHM KW")
    assert v["Bez2"] == "Zimmer 12"
    assert v["B3"] == "Bad, Waschbecken, Einhandmischarmatur"


def test_medium_konflikt_wird_schwach():
    s = scores("Zimmer 1 Waschbecken KW/WW")
    assert s["B4"] == 0.0 or s["B4"] < 0.75  # kein sicherer Wert bei KW+WW


def test_zellwert_etage_nummer():
    cells = CellMap(etage="5", raum="530", raumtyp="Patientenzimmer")
    v = values("5 | 530 | Patientenzimmer", cells)
    assert v["Bez2"] == "5. OG, Zimmer 530, Patientenzimmer"

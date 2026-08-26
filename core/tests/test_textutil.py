from lims_assistant.textutil import (
    fold_for_match,
    join_parts,
    levenshtein,
    sanitize_lims_value,
)


def test_sanitize_normalisiert_umbrueche_und_tabs_zu_einem_leerzeichen():
    assert sanitize_lims_value("Bad\r\nWaschbecken\tEHM") == "Bad Waschbecken EHM"
    assert sanitize_lims_value("  a \n\n b  ") == "a b"


def test_sanitize_leer_bleibt_leer_und_none_wird_leer():
    assert sanitize_lims_value("") == ""
    assert sanitize_lims_value(None) == ""
    assert sanitize_lims_value("   ") == ""


def test_sanitize_entfernt_steuerzeichen():
    assert sanitize_lims_value("A\x00B\x1fC") == "A B C"


def test_fold_for_match_faltet_umlaute_und_satzzeichen():
    assert fold_for_match("5. OG, Teeküche/WT") == "5 og teekueche wt"
    assert fold_for_match("Rücklauf-PNV") == "ruecklauf pnv"
    assert fold_for_match("Größe: ß") == "groesse ss"


def test_join_parts_ohne_haengende_trenner_oder_platzhalter():
    assert join_parts(["5. OG", "", "Patientenzimmer"]) == "5. OG, Patientenzimmer"
    assert join_parts(["", "", ""]) == ""
    assert join_parts(["Bad", "Waschbecken", "EHM"]) == "Bad, Waschbecken, EHM"
    assert join_parts([None, "Kaltwasser"]) == "Kaltwasser"


def test_levenshtein_grundfaelle():
    assert levenshtein("kueche", "kueche") == 0
    assert levenshtein("waschbekcen", "waschbecken") == 2
    assert levenshtein("abc", "abcd") == 1
    assert levenshtein("abc", "xyz", max_dist=1) == 2  # Abbruchwert max_dist+1

from lims_assistant.export.clipboard_text import column_copy_text


def test_leerzeilen_bleiben_positionshaltend():
    text = column_copy_text(["Kaltwasser", "", "Warmwasser, Speicher"])
    assert text == "Kaltwasser\r\n\r\nWarmwasser, Speicher"


def test_kein_header_und_kein_trailing_umbruch():
    text = column_copy_text(["a", "b"])
    assert not text.startswith("Bez")
    assert not text.endswith("\r\n")
    assert text.count("\r\n") == 1


def test_zellinterne_umbrueche_werden_zu_leerzeichen():
    text = column_copy_text(["Zeile\nmit Umbruch", "x"])
    assert text == "Zeile mit Umbruch\r\nx"


def test_einzelner_leerer_wert():
    assert column_copy_text([""]) == ""
    assert column_copy_text([]) == ""

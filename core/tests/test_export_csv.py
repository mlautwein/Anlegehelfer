import pytest

from lims_assistant.domain.entities import EXPORT_FILENAMES
from lims_assistant.export import csv_export
from lims_assistant.export.csv_export import encode_content, export_five, render_column

ROWS = [
    ["Haus A", "5. OG, Zimmer 530, Patientenzimmer", "Bad, Waschbecken, EHM", "Kaltwasser", "Legionellen"],
    ["Haus A", "", "", "", ""],  # leere Werte mittendrin
    ["Haus B", "EG, Küche", "Spüle, EHM", "Warmwasser, Speicher", ""],
]


def test_fuenf_dateien_headerlos_zeilengleich(tmp_path):
    files, hashes = export_five(ROWS, tmp_path)
    assert [f.split("/")[-1] for f in files] == list(EXPORT_FILENAMES)
    assert set(hashes) == set(EXPORT_FILENAMES)
    for i, name in enumerate(EXPORT_FILENAMES):
        content = (tmp_path / name).read_bytes()
        assert content.startswith(b"\xef\xbb\xbf")  # BOM
        text = content[3:].decode("utf-8")
        lines = text.split("\r\n")
        assert lines[-1] == ""  # terminierendes CRLF
        body = lines[:-1]
        assert len(body) == 3  # eine Zeile je Probe, KEIN Header
        assert body == [ROWS[0][i], ROWS[1][i], ROWS[2][i]]
    # leere Werte bleiben leere Zeilen an identischer Position
    unt = (tmp_path / "Untersuchungsart.csv").read_bytes()
    assert unt == b"\xef\xbb\xbfLegionellen\r\n\r\n\r\n"


def test_crlf_und_keine_lf_only(tmp_path):
    export_five(ROWS, tmp_path)
    raw = (tmp_path / "Bez2.csv").read_bytes()
    assert b"\r\n" in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")


def test_cp1252_umlaute_einbytig(tmp_path):
    export_five(ROWS, tmp_path, encoding="cp1252")
    raw = (tmp_path / "B3.csv").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")  # kein BOM bei cp1252
    assert b"Sp\xfcle" in raw  # ü als 0xFC


def test_cp1252_transliteration_typografischer_zeichen():
    data = encode_content("Wert – „Test“\r\n", "cp1252")
    assert b"-" in data and b'"Test"' in data


def test_vorhandene_dateien_werden_atomar_ersetzt(tmp_path):
    (tmp_path / "Bez1.csv").write_bytes(b"ALT")
    export_five(ROWS, tmp_path)
    assert b"ALT" not in (tmp_path / "Bez1.csv").read_bytes()


def test_teilfehler_laesst_ziele_unveraendert(tmp_path, monkeypatch):
    """Simulierter Fehler bei Datei 4: kein Ziel darf sich aendern."""
    for name in EXPORT_FILENAMES:
        (tmp_path / name).write_bytes(b"ORIGINAL")
    calls = {"n": 0}
    original = csv_export._write_tmp

    def failing(path, data):
        calls["n"] += 1
        if calls["n"] == 4:
            raise OSError("Datentraeger voll (simuliert)")
        original(path, data)

    monkeypatch.setattr(csv_export, "_write_tmp", failing)
    with pytest.raises(OSError):
        export_five(ROWS, tmp_path)
    for name in EXPORT_FILENAMES:
        assert (tmp_path / name).read_bytes() == b"ORIGINAL", name
    assert not list(tmp_path.glob("*.tmp")), "Temporaerdateien nicht bereinigt"


def test_zeilen_mit_falscher_spaltenzahl_abgelehnt(tmp_path):
    with pytest.raises(ValueError):
        export_five([["nur", "vier", "Werte", "hier"]], tmp_path)


def test_fehlender_zielordner(tmp_path):
    with pytest.raises(FileNotFoundError):
        export_five(ROWS, tmp_path / "gibts-nicht")


def test_werte_bleiben_woertlich_ohne_quoting():
    """Einspaltige LIMS-Zeilenlisten: Kommas/Anfuehrungszeichen sind Inhalt."""
    content = render_column(['mit "Anfuehrung"', "5. OG, Zimmer 530", "Zeile\numbruch", ""])
    lines = content.split("\r\n")
    assert lines[0] == 'mit "Anfuehrung"'
    assert lines[1] == "5. OG, Zimmer 530"
    assert lines[2] == "Zeile umbruch"
    assert lines[3] == ""


def test_leerer_export(tmp_path):
    files, _ = export_five([], tmp_path)
    for name in EXPORT_FILENAMES:
        data = (tmp_path / name).read_bytes()
        assert data == b"\xef\xbb\xbf"  # nur BOM, keine Zeilen

from lims_assistant.extract.patterns import (
    etage_rank,
    looks_like_metadata,
    natural_key,
    normalize_etage_cell,
    normalize_raum_cell,
    scan_etage,
    scan_objekt_header,
    scan_raum,
)


def test_scan_etage_varianten():
    assert scan_etage("5. OG links") == "5. OG"
    assert scan_etage("5.OG") == "5. OG"
    assert scan_etage("OG 3") == "3. OG"
    assert scan_etage("2. Obergeschoss") == "2. OG"
    assert scan_etage("Erdgeschoss") == "EG"
    assert scan_etage("Kellergeschoss") == "KG"
    assert scan_etage("2 UG") == "2. UG"
    assert scan_etage("Ebene 03") == "Ebene 3"
    assert scan_etage("Dachgeschoss rechts") == "DG"
    assert scan_etage("3. Etage") == "3. OG"
    assert scan_etage("ohne Angabe") == ""


def test_normalize_etage_cell_numerisch():
    assert normalize_etage_cell("5") == "5. OG"
    assert normalize_etage_cell("0") == "EG"
    assert normalize_etage_cell("-1") == "UG"
    assert normalize_etage_cell("-2") == "2. UG"
    assert normalize_etage_cell("EG") == "EG"
    assert normalize_etage_cell("Zwischenebene") == "Zwischenebene"  # Freitext erhalten


def test_etage_rank_ordnung():
    order = ["KG", "2. UG", "UG", "EG", "1. OG", "2. OG", "10. OG", "DG"]
    ranks = [etage_rank(e) for e in order]
    assert ranks == sorted(ranks)


def test_scan_raum():
    assert scan_raum("Zi. 530 Bad") == ("Zimmer", "530")
    assert scan_raum("Zimmer-Nr: 12a") == ("Zimmer", "12A")
    assert scan_raum("Raum U16") == ("Raum", "U16")
    assert scan_raum("R. 1.234") == ("Raum", "1.234")
    assert scan_raum("Rücklauf PNV") == ("", "")  # kein falscher Raum aus 'R'
    assert scan_raum("Nr. 17") == ("", "")


def test_normalize_raum_cell():
    assert normalize_raum_cell("530", zimmer_context=True) == "Zimmer 530"
    assert normalize_raum_cell("U16") == "Raum U16"
    assert normalize_raum_cell("Zimmer 530") == "Zimmer 530"
    assert normalize_raum_cell("Whg 1 Bad") == "Whg 1 Bad"  # beschreibend erhalten


def test_natural_key_sortiert_natuerlich():
    values = ["Zimmer 9", "Zimmer 10", "Zimmer 2"]
    assert sorted(values, key=natural_key) == ["Zimmer 2", "Zimmer 9", "Zimmer 10"]


def test_objekt_header_und_metadaten():
    assert scan_objekt_header("Objekt: Klinik Moselhoehe") == "Klinik Moselhoehe"
    assert scan_objekt_header("Gebäude - Haus B") == "Haus B"
    assert scan_objekt_header("Zimmer 12") == ""
    assert looks_like_metadata("Seite 2 von 3")
    assert looks_like_metadata("Datum: 24.08.2026")
    assert not looks_like_metadata("EG Küche Spüle EHM")

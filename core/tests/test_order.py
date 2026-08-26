from lims_assistant.normalize.order import sort_key, sorted_permutation, split_bez2


def test_split_bez2():
    assert split_bez2("5. OG, Zimmer 530, Patientenzimmer") == (
        "5. OG",
        "Zimmer 530, Patientenzimmer",
    )
    assert split_bez2("EG, Küche") == ("EG", "Küche")
    assert split_bez2("Zimmer 12") == ("", "Zimmer 12")
    assert split_bez2("") == ("", "")


def test_sortierung_bez1_etage_raum():
    rows = [
        ("Haus B", "EG, Küche"),
        ("Haus A", "2. OG, Zimmer 10, Bad"),
        ("Haus A", "EG, Zimmer 2"),
        ("Haus A", "2. OG, Zimmer 9, Bad"),
        ("Haus A", "UG, Technikraum"),
        ("Haus A", "KG, Heizungsraum"),
    ]
    perm = sorted_permutation(rows)
    ordered = [rows[i] for i in perm]
    assert ordered == [
        ("Haus A", "KG, Heizungsraum"),
        ("Haus A", "UG, Technikraum"),
        ("Haus A", "EG, Zimmer 2"),
        ("Haus A", "2. OG, Zimmer 9, Bad"),
        ("Haus A", "2. OG, Zimmer 10, Bad"),
        ("Haus B", "EG, Küche"),
    ]


def test_sortierung_stabil_bei_duplikaten():
    rows = [("A", "EG, Raum 1")] * 3 + [("A", "EG, Raum 0")]
    perm = sorted_permutation(rows)
    assert perm == [3, 0, 1, 2]  # Duplikate behalten relative Reihenfolge


def test_quellreihenfolge_wiederherstellbar():
    rows = [("B", "EG"), ("A", "EG"), ("C", "EG")]
    perm = sorted_permutation(rows)
    restore = sorted(range(len(perm)), key=lambda i: perm[i])
    round_trip = [[rows[i] for i in perm][j] for j in restore]
    assert round_trip == rows


def test_sort_key_unbekannte_etage_ans_ende():
    assert sort_key("A", "Zwischenebene, Raum 1") > sort_key("A", "DG, Raum 1")

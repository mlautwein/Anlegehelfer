"""Deutsche Fachvokabulare fuer Trinkwasser-Probenstellen.

Alle Synonyme werden in gefalteter Form (klein, ae/oe/ue/ss, ohne
Satzzeichen) gefuehrt und gegen gefaltete Texte gematcht. Die kanonische
Form (mit Umlauten) ist der Ausgabewert. Vokabulare sind bewusst offen:
unbekannte Begriffe blockieren nichts, sie bleiben Freitext.
"""

from __future__ import annotations

from lims_assistant.textutil import fold_for_match, levenshtein

# Kanonisch -> gefaltete Synonyme (die kanonische Form selbst wird automatisch
# in gefalteter Form ergaenzt).

WASSERSTELLE: dict[str, list[str]] = {
    "Waschbecken": ["wb", "waschtisch", "wt", "handwaschbecken", "hwb", "waschbecke"],
    "Spüle": ["spuele", "spuelbecken", "kuechenspuele"],
    "Dusche": ["du", "duschkopf", "duschbrause"],
    "Badewanne": ["wanne", "bw", "wanneneinlauf"],
    "Ausgussbecken": ["ausguss", "ausgussbecke"],
    "Entnahmeventil": ["ev", "entnahmehahn"],
    "Zapfstelle": ["zapfhahn", "zapfventil"],
    "Trinkbrunnen": ["trinkwasserspender", "wasserspender"],
}

ARMATUR: dict[str, list[str]] = {
    "Einhandmischarmatur": [
        "ehm",
        "einhandmischer",
        "einhebelmischer",
        "einhebelmischarmatur",
        "einhandhebelmischer",
    ],
    "Zweigriffarmatur": ["zweigriff", "zweigriffmischer", "zweigriffmischarmatur"],
    "Thermostatarmatur": ["thermostat", "thermostatmischer", "thermostatbatterie"],
    "Selbstschlussarmatur": ["selbstschluss", "selbstschlussventil"],
    "Wandauslaufventil": ["wandauslauf", "wandventil", "wandarmatur"],
    "Standventil": ["standarmatur"],
    "Brausearmatur": ["duscharmatur", "brause", "brausebatterie"],
}

PNV_TOKENS = {"pnv", "probenahmeventil", "probeentnahmeventil", "probennahmeventil"}

ORT: dict[str, list[str]] = {
    "Bad": ["badezimmer", "bad"],
    "WC": ["toilette", "wc"],
    "Küche": ["kueche"],
    "Teeküche": ["teekueche"],
    "Waschraum": ["waschraum"],
    "Duschraum": ["duschraum"],
    "Putzraum": ["putzraum", "putzmittelraum"],
}

RAUMTYP: dict[str, list[str]] = {
    "Patientenzimmer": ["patientenzimmer", "pat zimmer", "pat zi", "patzimmer"],
    "Arztzimmer": ["arztzimmer"],
    "Dienstzimmer": ["dienstzimmer"],
    "Schwesternzimmer": ["schwesternzimmer"],
    "Stationszimmer": ["stationszimmer"],
    "Untersuchungsraum": ["untersuchungsraum"],
    "Behandlungsraum": ["behandlungsraum", "behandlungszimmer"],
    "Teeküche": ["teekueche"],
    "Küche": ["kueche", "grosskueche", "zentralkueche"],
    "Bad": ["badezimmer", "pflegebad"],
    "WC": ["toilette", "besucher wc", "gaeste wc"],
    "Personal-WC": ["personal wc", "personalwc", "pers wc", "mitarbeiter wc"],
    "Technikraum": ["technikraum", "technikzentrale", "tga zentrale", "technik"],
    "Heizungsraum": ["heizungsraum", "heizraum", "heizungskeller", "heizzentrale"],
    "Hausanschlussraum": ["hausanschlussraum", "har", "hausanschluss"],
    "Lager": ["lagerraum", "lager"],
    "Putzraum": ["putzraum", "putzmittelraum", "reinigungsraum"],
    "Büro": ["buero", "bueroraum"],
    "Flur": ["flur", "gang", "stationsflur"],
    "Wohnung": ["wohnung", "whg"],
    "Waschküche": ["waschkueche"],
    "Duschraum": ["duschraum", "duschen"],
    "Umkleide": ["umkleide", "umkleideraum"],
    "Labor": ["labor", "laborraum"],
    "Werkstatt": ["werkstatt"],
    "Aufenthaltsraum": ["aufenthaltsraum", "aufenthalt"],
    "Bewohnerzimmer": ["bewohnerzimmer"],
    "Gästezimmer": ["gaestezimmer"],
    "Klassenraum": ["klassenraum", "klassenzimmer"],
    "Gruppenraum": ["gruppenraum"],
}

# Raumtypen mit ueberwiegend technischen Entnahmestellen.
TECH_RAUMTYPEN = {
    "Technikraum",
    "Heizungsraum",
    "Hausanschlussraum",
}

MEDIUM_KALT = {"kw", "twk", "pwc", "kaltwasser", "kaltw", "kalt", "trinkwasser kalt"}
MEDIUM_WARM = {"ww", "tww", "pwh", "warmwasser", "warmw", "warm", "trinkwasser warm"}

ZUSATZ_ZIRK = {"zirkulation", "zirk", "zirku", "pwh c", "pwhc", "zirkulationsleitung", "zp"}
ZUSATZ_SPEICHER = {
    "speicher",
    "wwsp",
    "twe speicher",
    "trinkwarmwasserspeicher",
    "warmwasserspeicher",
    "boiler",
    "pufferspeicher",
}
ZUSATZ_DLE = {"dle", "durchlauferhitzer", "e dle", "elektro durchlauferhitzer"}

VL_TOKENS = {"vl", "vorlauf"}
RL_TOKENS = {"rl", "ruecklauf"}

TECH_HINWEIS = (
    VL_TOKENS
    | RL_TOKENS
    | ZUSATZ_ZIRK
    | ZUSATZ_SPEICHER
    | ZUSATZ_DLE
    | PNV_TOKENS
    | {
        "steigstrang",
        "strang",
        "verteiler",
        "uebergabestation",
        "waermetauscher",
        "twe",
        "druckminderer",
        "wasserzaehler",
        "hauswasserstation",
        "enthaertung",
        "enthaertungsanlage",
    }
)

UNTERSUCHUNG: dict[str, list[str]] = {
    "Legionellen": [
        "legionellen",
        "legionella",
        "leg",
        "legionellenpruefung",
        "legionellenuntersuchung",
        "legionellenbeprobung",
        "trinkwv legionellen",
    ],
    "Mikrobiologische Untersuchung": [
        "mikrobiologische untersuchung",
        "mikrobiologie",
        "mibi",
        "mikrobiologisch",
        "e coli",
        "coliforme",
        "kbe",
        "gesamtkeimzahl",
        "koloniezahl",
    ],
    "Chemische Untersuchung": ["chemie", "chemisch", "chemische untersuchung"],
}


def _folded_map(vocab: dict[str, list[str]]) -> dict[str, str]:
    """gefaltetes Synonym -> kanonische Form (laengere Synonyme zuerst matchen)."""
    out: dict[str, str] = {}
    for canon, syns in vocab.items():
        for syn in [fold_for_match(canon), *syns]:
            if syn:
                out[syn] = canon
    return out


WASSERSTELLE_MAP = _folded_map(WASSERSTELLE)
ARMATUR_MAP = _folded_map(ARMATUR)
ORT_MAP = _folded_map(ORT)
RAUMTYP_MAP = _folded_map(RAUMTYP)
UNTERSUCHUNG_MAP = _folded_map(UNTERSUCHUNG)


def match_vocab(folded_text: str, mapping: dict[str, str]) -> str | None:
    """Findet die beste (laengste) Synonym-Uebereinstimmung mit Wortgrenzen."""
    if not folded_text:
        return None
    padded = f" {folded_text} "
    best: tuple[int, str] | None = None
    for syn, canon in mapping.items():
        if f" {syn} " in padded:
            if best is None or len(syn) > best[0]:
                best = (len(syn), canon)
    return best[1] if best else None


def match_vocab_fuzzy(
    folded_text: str, mapping: dict[str, str], *, min_len: int = 5
) -> str | None:
    """Fuzzy-Reparatur einzelner (OCR-)Woerter gegen laengere Vokabelworte.

    Distanz 1 fuer 5-7 Zeichen, Distanz 2 ab 8 Zeichen. Nur Einzelwoerter.
    """
    tokens = folded_text.split()
    best: tuple[int, int, str] | None = None  # (dist, -len, canon)
    for token in tokens:
        if len(token) < min_len:
            continue
        for syn, canon in mapping.items():
            if " " in syn or len(syn) < min_len:
                continue
            limit = 1 if len(syn) < 8 else 2
            if abs(len(token) - len(syn)) > limit:
                continue
            d = levenshtein(token, syn, max_dist=limit)
            if d <= limit:
                cand = (d, -len(syn), canon)
                if best is None or cand < best:
                    best = cand
    return best[2] if best else None


def any_token(folded_text: str, tokens: set[str]) -> bool:
    padded = f" {folded_text} "
    return any(f" {t} " in padded for t in tokens)

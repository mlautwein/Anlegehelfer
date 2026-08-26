# JSON-Vertraege (schema_version 1.0)

Die Dateien unter `schemas/` werden aus den Pydantic-Modellen generiert
(`lims-core export-schemas --out contracts/schemas`) und sind durch einen
Contract-Test gegen Drift gesichert (`core/tests/test_contracts.py`).

## Envelopes

`JobRequest` (`request.json`): `schema_version`, `job_id`, `kind`,
`created_utc`, `payload`. Inkompatible Major-Versionen werden abgelehnt;
unbekannte Felder ueberall verboten.

`JobProgress` (`progress.json`): `phase`, `percent`, `message`,
`cancellable`, `done` - wird waehrend der Analyse fortlaufend atomar
ueberschrieben.

`JobResponse` (`response.json`): `ok`, `error {code, message, detail}`,
`result` (kind-spezifisch). Fehlercodes: `bad_request`, `not_found`,
`cancelled`, `sync_error`, `timeout` (VBA-seitig), `internal`.

## Kinds und Ergebnisse

| kind | Zweck | Ergebnis-Kern |
|---|---|---|
| `list_sheets` | Excel-Blaetter auflisten | `sheets[{name, visible, rows, cols}]`, `has_macros` |
| `analyze` | Quellen analysieren, Zeilen anhaengen | `session_id`, `export_base_dir`, `rows[]`, `warnings[]`, `stats` |
| `apply_revision` | direkte Zellkorrektur lernen | `event_id`, `learned` |
| `row_event` | Zeile hinzufuegen/loeschen | `event_id` |
| `confirm_cells` | Copy/Export-Bestaetigung (idempotent) | `confirmed`, `new_examples`, `duplicates` |
| `undo` | letzte Aktion kompensieren | `compensated_event_id`, `compensated_kind` |
| `rebuild_learning` | Indizes aus aktiver Historie neu | Zaehler + `index_hash`, `row_model_hash` |
| `export_csv` | atomarer Fuenffach-Export | `files[]`, `row_count`, `target_dir` |
| `app_open` | Lock + Snapshot-Pull/Pending-Push | `lock_acquired`, `read_only`, `lock`, `warnings` |
| `app_close` | Snapshot-Push + Lock-Freigabe | `snapshot_pushed`, `pending`, `lock_released` |
| `health` | Selbstauskunft/Integritaet | Versionen, OCR/LLM/Lern-/Lock-Status, `offline_guard` |

## Ergebniszeile

    {
      "row_id": "uuid",
      "source_order": 17,
      "fields": {
        "Bez1":  {"value": "...", "is_uncertain": false},
        "Bez2":  {"value": "...", "is_uncertain": false},
        "B3":    {"value": "...", "is_uncertain": true},
        "B4":    {"value": "...", "is_uncertain": false},
        "Untersuchungsart": {"value": "...", "is_uncertain": true}
      }
    }

Genau fuenf Felder; `""` ist gueltig und positionshaltend; Zeilenumbrueche
und Tabs innerhalb eines Werts werden deterministisch zu genau einem
Leerzeichen normalisiert (Kontrakt-Validator + Export + VBA).

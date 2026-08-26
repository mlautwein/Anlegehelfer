# Sicherheit, Datenschutz, Robustheit

| Risiko | Umsetzung im Code | Nachweis (Tests) |
|---|---|---|
| Cloud-/Datenabfluss | Offline-Waechter blockiert alle Sockets ausser Loopback (`net_guard.py`, im CLI-Produktivmodus aktiv); keine Telemetrie; kein Laufzeit-Download | `test_net_guard.py`, `test_jobs_e2e.py::test_offline_guard_im_produktivmodus_aktiv` |
| Prompt Injection im Dokument | Injektionszeilen erreichen als Nicht-Probenzeilen das LLM gar nicht; Systemprompt trennt Anweisung/DATEN; JSON-Schema erzwungen; Antwort pydantic-validiert, laengenbegrenzt, nur Lueckenfelder | `test_ingest_pdf.py::test_prompt_injection_wird_nicht_uebernommen`, `test_llm_adapter.py` |
| Makros in Quelldateien | XLSX/XLSM/XLS werden nur als Datencontainer geparst (openpyxl/xlrd, reine Parser ohne Ausfuehrungspfad); vbaProject wird erkannt und gemeldet, nie geladen | `test_ingest_excel.py::test_xlsm_wird_gelesen_aber_makros_nie_ausgefuehrt` |
| Excel-Formelinjektion | Zielzellen werden vor jeder Zuweisung als Text formatiert (`NumberFormat "@"`); Werte kommen nur ueber `.Value` | VBA `modErgebnisse`/`modSetup`; Abnahme C8 |
| Pfad-/Shell-Injektion | Prozessstart ausschliesslich mit manifestierten Pfaden; Benutzerdaten (Pfade, Texte) reisen nur in JSON-Dateien | `modJobClient.bas`, `vba_lint.py` (verbotene Muster) |
| Beschaedigter Shared-Snapshot | SHA-256-Manifest, atomarer Replace, rollierende Backups, lokale Pending-Kopie; korrupter Snapshot wird erkannt statt uebernommen | `test_lock_sync.py` |
| Parallelzugriff | Exklusiver Lock (O_CREAT\|O_EXCL) mit Nonce + Heartbeat; zweiter Start nur lesend; stale nur nach Benutzerentscheidung | `test_lock_sync.py`, `test_runner_handlers.py` |
| Temporaere Originale | Job-Tempverzeichnisse mit finally-Cleanup; Start-Sweep verwaister Reste; Originalbytes werden nie in DB/Share kopiert | `test_jobs_e2e.py::test_keine_originaldateien_im_datenverzeichnis` |
| Unsichere KI-Ableitung | Gelb ausschliesslich nach Provenienz-/Schwellwert-/OCR-/Konfliktregel; Retrieval/LLM/Zusatztext immer gelb; keine unkalibrierte LLM-Selbsteinschaetzung | `test_zusatz.py`, `test_llm_adapter.py`, `fusion/fuse.py` |
| Veraltete Office-Plattform | Excel 2016 wird unterstuetzt (VBA7/PtrSafe/LongPtr), das Support-Ende (14.10.2025) ist dokumentiertes Betriebsrisiko; mittelfristige Office-Migration einplanen | Spezifikation Q10; `docs/ABNAHME_EXCEL2016.md` |

## Datenhaltung

Gespeichert werden: vollstaendig extrahierter Text, Zusatztexte,
Lern-/Bedienereignisse, Feldvorschlaege mit Provenienz - bis zur manuellen
Loeschung. NICHT gespeichert werden Originaldateibytes. Einzelne
Lernbeispiele lassen sich deaktivieren/loeschen (Feld `active` bzw.
Loeschung in `learning_example`), danach stellt `rebuild_learning` den
Index reproduzierbar aus der verbleibenden aktiven Historie her
(Inhalts-Hashes im Ergebnis).

Es gibt keine Benutzerkonten und keine personenbezogene
Korrekturzuordnung; die Lockdatei enthaelt nur den Computernamen fuer die
"belegt durch"-Anzeige.

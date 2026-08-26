# Modellvergleich (Implementierungs-Gate)

Die Produktionswahl des lokalen Sprachmodells erfolgt ausschliesslich ueber
diesen reproduzierbaren Benchmark. Bis dahin bleibt `llm.enabled=false`;
die Anwendung ist ohne LLM voll funktionsfaehig (deterministische Pipeline +
fallbasiertes Lernen decken den Normalbetrieb).

## Kandidaten

| Kandidat | Rolle | Lizenz | Status |
|---|---|---|---|
| Qwen3-4B-Instruct-2507, Q4_K_M GGUF | Referenzkandidat | Apache-2.0 | provisionieren + messen |
| Phi-4 Mini Instruct, Q4 GGUF | sehr guter Fallback | MIT | provisionieren + messen |
| Phi-3 Mini 4k Instruct, Q4 GGUF | Legacy-Baseline | MIT | provisionieren + messen |
| Gemma 3 4B it (QAT), Q4 GGUF | Benchmark-Kandidat | Gemma-Nutzungsbedingungen | provisionieren + messen |

Laufzeit: llama.cpp `llama-server` (Windows x64, CPU/AVX2), Release-Build
gepinnt; schema-beschraenkte JSON-Ausgabe (`response_format=json_schema`).

## Messgroessen (identischer deutscher Korpus, `scripts/benchmark_llm.py`)

Zeilen-Precision/Recall/F1 uebernimmt der Pipeline-Benchmark; der
LLM-Benchmark misst je Kandidat: valide JSON-Schema-Antworten, exakte und
normalisierte Feldtreffer, Zeichen-Edit-Distanz, Verhalten bei leeren,
widerspruechlichen und prompt-injection-artigen Zeilen (Injektionszaehler
muss 0 sein), CPU-Laufzeit p50/p95 sowie Peak-RAM. Zusaetzlich auf der
Zielhardware: Kaltstartzeit des Servers.

## Ablauf

1. Kandidaten provisionieren (`packaging/windows/provision_offline.ps1`),
   SHA-256 in `packaging/models/manifest.json` eintragen.
2. Je Kandidat: `python scripts/benchmark_llm.py --model <gguf> --server
   <llama-server> --name <id> --out docs/benchmarks/llm-<id>.md`
3. Ergebnisse in die Tabelle unten uebertragen; Gewinner pinnen
   (Modell-ID, Hash, Quantisierung, Lizenz, llama.cpp-Version).
4. Spaeter mit echten anonymisierten Pilotdaten wiederholen, bevor
   Genauigkeitsaussagen gemacht werden.

## Ergebnisse

| Kandidat | Schema-valide | Exact | Norm. | Edit Ø | Injektionen | p50 | p95 | Peak-RAM | Datum/Host |
|---|---|---|---|---|---|---|---|---|---|
| Harness-Verifikation (Fake-Adapter) | 1/1 | 1.000 | 1.000 | 0 | 0 | <0,01 s | - | - | 2026-08-26 Dev-Sandbox |
| Qwen3-4B-Instruct-2507 Q4_K_M | _ausstehend_ | | | | | | | | |
| Phi-4 Mini Q4 | _ausstehend_ | | | | | | | | |
| Phi-3 Mini Q4 (Baseline) | _ausstehend_ | | | | | | | | |
| Gemma 3 4B Q4 | _ausstehend_ | | | | | | | | |

**Produktionsentscheidung: OFFEN** - in der Entwicklungsumgebung war kein
Modell-Download moeglich (huggingface.co gesperrt); die Messung ist als
erster Schritt der Windows-Provisionierung eingeplant. Erfundene
Genauigkeitswerte gibt es hier bewusst nicht.

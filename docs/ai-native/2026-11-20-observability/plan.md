# Plan: osservabilità e verifica del deploy

Deriva da `spec.md` nella stessa cartella. Branch `feat/observability`.

**Goal:** rendere verificabile la release, automatizzare uno smoke test senza
LLM e rendere i log sufficienti per latenza, errori e token.

## Task

### Task 1 — Identità della release

**File:** `backend/app/version.py` (nuovo), `backend/app/main.py`,
`backend/tests/test_version.py` (nuovo).

- [x] `COMMIT_SHA` da `VERCEL_GIT_COMMIT_SHA`, poi `GIT_COMMIT_SHA`, poi
  `"unknown"`; `BUILD_TIME` da `BUILD_TIME`, poi `"unknown"`.
- [x] `/health` restituisce `status`, `commit`, `built_at`.
- [x] Test: `status` invariato, i due campi presenti; `unknown` accettato.
- [x] Eseguire.

### Task 2 — Usage della chat

**File:** `backend/graph/chat_graph.py`, `backend/tests/test_usage.py` (nuovo).

- [x] `_usage(message)` legge `usage_metadata` (`input_tokens`/`output_tokens`/
  `total_tokens`, fallback `prompt_tokens`/`completion_tokens`).
- [x] `_merge_usage` somma due dict.
- [x] Accumulo in `nodo_riscrivi_query`, `nodo_genera_meta`,
  `nodo_espandi_query`, `_genera`; `ChatState` ha `usage`.
- [x] `run_chat` restituisce `usage`.
- [x] Test con un fake LLM che restituisce `usage_metadata`: la somma è corretta
  e le chiavi mancanti valgono 0.

### Task 3 — Usage della semplificazione

**File:** `backend/services/simplify.py`, `backend/tests/test_usage.py`.

- [x] `_chiama_modello` allega l’usage alla risposta normalizzata.
- [x] `_merge` somma l’usage delle parti; il fallback ha usage zero.
- [x] Test: due chunk producono la somma; cache hit non raddoppia.
- [x] La route logga `prompt_tokens`, `completion_tokens`, `total_tokens` per
  chat e simplify.

### Task 4 — Smoke test

**File:** `scripts/smoke.py` (nuovo), `backend/tests/test_smoke_script.py`
(nuovo), `.github/workflows/smoke.yml` (nuovo), `Makefile`.

- [x] Funzione `run_checks(base_url, timeout, require_commit, fetch=...)` con i
  sette check della spec; nessuna chiamata valida all’LLM.
- [x] CLI con `--base-url`, `--timeout`, `--require-commit`; exit 1 se un check
  fallisce.
- [x] Test con un `fetch` finto: scenario sano, scenario vecchio backend
  (chat vuota 200), scenario Qdrant giù (warning non errore).
- [x] `make smoke`.
- [x] Workflow giornaliero + `workflow_dispatch`, senza segreti.

### Task 5 — Report dai log

**File:** `scripts/log_report.py` (nuovo), `backend/tests/test_log_report.py`
(nuovo), `Makefile`.

- [x] Parser JSONL tollerante alle righe non JSON.
- [x] `summarize(eventi)` → totali, status, 429, 5xx, p50/p95, token per
  modello, cache hit.
- [x] CLI `--json`, `--max-tokens`, `--max-errors`, `--max-429`,
  `--usd-per-1m-input`, `--usd-per-1m-output`; exit 1 sulle soglie.
- [x] Test con un campione di eventi.
- [x] `make report-logs LOGS=...`.

### Task 6 — Runbook e documentazione

**File:** `docs/ai-native/2026-11-20-observability/runbook.md`,
`AGENTS.md`, `README.md`.

- [x] Drain Vercel → Better Stack, export, comando report, soglia e owner.
- [x] Sequenza deploy: `vercel --prod` → `make smoke` → confronto SHA.
- [x] Cosa fare se lo smoke fallisce e come rollbackare.
- [x] Comandi `make smoke` e `make report-logs` in README/AGENTS.

### Task 7 — Verifica, merge, deploy

- [x] `make test`, `make check`.
- [x] Smoke locale contro `http://127.0.0.1:8000` (backend avviato).
- [x] Commit, merge fast-forward in `main`, push.
- [x] `vercel --prod`, poi `make smoke` contro produzione e confronto SHA.
- [x] Aggiornare questo piano con i risultati.

## Rischi

| Rischio | Mitigazione |
|---|---|
| Lo smoke test dipende dalla rete | Timeout per check e messaggi espliciti |
| Usage non disponibile | Campi a 0; il report conta gli eventi senza usage |
| Log drain non configurato | Il report legge un file; il drain è opzionale |
| Workflow giornaliero rumoroso | Solo fallimenti notificano; nessun segreto |

## Prove

| Comando | Atteso |
|---|---|
| `uv run pytest -q tests/test_version.py tests/test_usage.py tests/test_smoke_script.py tests/test_log_report.py` | verdi |
| `make test` | verdi |
| `make check` | verdi + checker `OK` |
| `python3 scripts/smoke.py` | tutti i check verdi contro produzione |
| `python3 scripts/log_report.py --help` | opzioni disponibili |

## Risultato (2026-11-20)

- `make test`: **210 passed** (191 esistenti + 19 nuovi).
- `make check`: verde, Ruff pulito, build a 18 route, checker `OK`.
- Smoke locale (`--backend`): 6/6, `commit=unknown` come atteso fuori da
  Vercel.
- Deploy Production del commit `f191ed1`; smoke produzione: **7/7**;
  `/api/health` restituisce `commit=f191ed1…` uguale a `HEAD`.
- `built_at` è `unknown`: Vercel espone lo SHA ma non un timestamp di build.
  Lo SHA è il campo autorevole; `BUILD_TIME` è opzionale.
- Il workflow `Production smoke` è attivo con `--require-commit`.

## Task 8 — Export su Hobby (2026-11-20)

- [x] Verificato il piano del team: Hobby; Drains richiedono Pro; retention 1 h.
- [x] `StructuredFormatter` e `configure_logging()`: JSON puro per
  `app.observability`, prefisso invariato per gli altri logger.
- [x] `normalize_record`, `record_key`, deduplica in `log_report.py`.
- [x] `scripts/export_logs.py` con `--since`, `--limit`, `--output`, `--append`,
  `--project`, `--scope`; token solo da `VERCEL_TOKEN`.
- [x] Workflow `Log export` ogni 30 minuti, artifact 30 giorni, `--max-errors 0`.
- [x] Test: 4 su `export_logs`, 3 sull'envelope Vercel, 2 sul formatter.

Prove: export reale di 40 minuti → 1 evento normalizzato, report con p50/p95;
secondo export con `--append` → 0 duplicati. `make check` verde.

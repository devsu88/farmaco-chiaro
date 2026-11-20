# Plan: osservabilità e verifica del deploy

Deriva da `spec.md` nella stessa cartella. Branch `feat/observability`.

**Goal:** rendere verificabile la release, automatizzare uno smoke test senza
LLM e rendere i log sufficienti per latenza, errori e token.

## Task

### Task 1 — Identità della release

**File:** `backend/app/version.py` (nuovo), `backend/app/main.py`,
`backend/tests/test_version.py` (nuovo).

- [ ] `COMMIT_SHA` da `VERCEL_GIT_COMMIT_SHA`, poi `GIT_COMMIT_SHA`, poi
  `"unknown"`; `BUILD_TIME` da `BUILD_TIME`, poi `"unknown"`.
- [ ] `/health` restituisce `status`, `commit`, `built_at`.
- [ ] Test: `status` invariato, i due campi presenti; `unknown` accettato.
- [ ] Eseguire.

### Task 2 — Usage della chat

**File:** `backend/graph/chat_graph.py`, `backend/tests/test_usage.py` (nuovo).

- [ ] `_usage(message)` legge `usage_metadata` (`input_tokens`/`output_tokens`/
  `total_tokens`, fallback `prompt_tokens`/`completion_tokens`).
- [ ] `_merge_usage` somma due dict.
- [ ] Accumulo in `nodo_riscrivi_query`, `nodo_genera_meta`,
  `nodo_espandi_query`, `_genera`; `ChatState` ha `usage`.
- [ ] `run_chat` restituisce `usage`.
- [ ] Test con un fake LLM che restituisce `usage_metadata`: la somma è corretta
  e le chiavi mancanti valgono 0.

### Task 3 — Usage della semplificazione

**File:** `backend/services/simplify.py`, `backend/tests/test_usage.py`.

- [ ] `_chiama_modello` allega l’usage alla risposta normalizzata.
- [ ] `_merge` somma l’usage delle parti; il fallback ha usage zero.
- [ ] Test: due chunk producono la somma; cache hit non raddoppia.
- [ ] La route logga `prompt_tokens`, `completion_tokens`, `total_tokens` per
  chat e simplify.

### Task 4 — Smoke test

**File:** `scripts/smoke.py` (nuovo), `backend/tests/test_smoke_script.py`
(nuovo), `.github/workflows/smoke.yml` (nuovo), `Makefile`.

- [ ] Funzione `run_checks(base_url, timeout, require_commit, fetch=...)` con i
  sette check della spec; nessuna chiamata valida all’LLM.
- [ ] CLI con `--base-url`, `--timeout`, `--require-commit`; exit 1 se un check
  fallisce.
- [ ] Test con un `fetch` finto: scenario sano, scenario vecchio backend
  (chat vuota 200), scenario Qdrant giù (warning non errore).
- [ ] `make smoke`.
- [ ] Workflow giornaliero + `workflow_dispatch`, senza segreti.

### Task 5 — Report dai log

**File:** `scripts/log_report.py` (nuovo), `backend/tests/test_log_report.py`
(nuovo), `Makefile`.

- [ ] Parser JSONL tollerante alle righe non JSON.
- [ ] `summarize(eventi)` → totali, status, 429, 5xx, p50/p95, token per
  modello, cache hit.
- [ ] CLI `--json`, `--max-tokens`, `--max-errors`, `--max-429`,
  `--usd-per-1m-input`, `--usd-per-1m-output`; exit 1 sulle soglie.
- [ ] Test con un campione di eventi.
- [ ] `make report-logs LOGS=...`.

### Task 6 — Runbook e documentazione

**File:** `docs/ai-native/2026-11-20-observability/runbook.md`,
`AGENTS.md`, `README.md`.

- [ ] Drain Vercel → Better Stack, export, comando report, soglia e owner.
- [ ] Sequenza deploy: `vercel --prod` → `make smoke` → confronto SHA.
- [ ] Cosa fare se lo smoke fallisce e come rollbackare.
- [ ] Comandi `make smoke` e `make report-logs` in README/AGENTS.

### Task 7 — Verifica, merge, deploy

- [ ] `make test`, `make check`.
- [ ] Smoke locale contro `http://127.0.0.1:8000` (backend avviato).
- [ ] Commit, merge fast-forward in `main`, push.
- [ ] `vercel --prod`, poi `make smoke` contro produzione e confronto SHA.
- [ ] Aggiornare questo piano con i risultati.

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

# Spec: osservabilità e verifica del deploy

Data: 2026-11-20. Deriva da `intent.md` nella stessa cartella. Decisioni
confermate dal maintainer: log drain con free tier, budget con alert,
`/health` con SHA, smoke test dopo il deploy e giornaliero, deploy Production
manuale.

## Obiettivo

Sapere **quale codice sta girando**, **se funziona** e **quanto costa**, senza
automatizzare il deploy né introdurre un servizio obbligatorio.

## Requisiti

### R1 — Identità della release

`GET /health` restituisce, oltre a `status`:

```json
{
  "status": "healthy",
  "commit": "9ebee84",
  "built_at": "2026-11-20T07:45:00Z"
}
```

`commit` viene da `VERCEL_GIT_COMMIT_SHA`, poi `GIT_COMMIT_SHA`, altrimenti
`"unknown"`. `built_at` viene da `BUILD_TIME`, altrimenti `"unknown"`.
Il contratto esistente (`status`) resta invariato.

### R2 — Smoke test senza LLM

`scripts/smoke.py` accetta `--base-url` (default
`https://farmaco-chiaro.vercel.app`), `--timeout` (default 15 s) e
`--require-commit`. Verifica:

1. `GET /health` → 200, `status == "healthy"`; se `--require-commit`, `commit`
   non è `"unknown"`.
2. `GET /api/rag/status` → 200, `farmaci > 0`; `qdrant.available` falso è un
   warning, non un errore (il fallback BM25 è voluto).
3. `GET /api/farmaco/012745_01` → 200.
4. `GET /farmaco/012745_01` → 200.
5. `GET /api/rag/status` include `X-Request-ID`.
6. `POST /api/chat` con `messaggio: ""` → 422.
7. `POST /api/chat` con 1.001 caratteri → 422.

Nessuna chiamata valida all’LLM. Esce 0 se tutto passa, 1 al primo gruppo di
errori; stampa una riga per check. `make smoke` lo esegue.

Un workflow GitHub `smoke.yml` lo esegue ogni giorno e su `workflow_dispatch`,
senza segreti.

### R3 — Report dai log

`scripts/log_report.py` legge JSONL da file o stdin e produce:

- richieste totali, conteggio per status, `429`, `5xx`;
- p50 e p95 di `duration_ms` per `http_request`;
- token `prompt`/`completion`/`total` per modello, dai campi dei log;
- cache hit (`simplify_completed` con `cached: true`);
- costo stimato opzionale con `--usd-per-1m-input` e
  `--usd-per-1m-output` (default 0, free tier).

Soglie: `--max-tokens N`, `--max-errors N`, `--max-429 N`; se superate esce 1.
`--json` produce JSON invece della tabella. `make report-logs LOGS=...` lo
esegue.

### R4 — Token usage nei log

- Chat: il grafo accumula l’usage di tutte le chiamate (riscrittura, meta,
  espansione, generazione) e lo restituisce in `run_chat` come `usage`; la
  route logga `prompt_tokens`, `completion_tokens`, `total_tokens`.
- Simplify: `_chiama_modello` restituisce l’usage della chiamata, `_merge` lo
  somma sulle parti; la route logga i totali. Un cache hit logga 0 token.
- Se il provider non restituisce usage, i campi valgono 0.
- `ChatResponse` e `SimplifyResponse` non espongono l’usage: il contratto
  pubblico resta invariato.

### R5 — Runbook

`runbook.md` nella cartella dell’iniziativa spiega:

- come collegare il log drain Vercel a Better Stack (free tier) e verificarlo;
- come esportare i log e lanciare il report;
- come impostare la soglia di budget e chi riceve l’alert;
- la sequenza di deploy: `vercel --prod` → `make smoke` → confronto SHA;
- cosa fare se lo smoke test fallisce.

## Design

### File

- `backend/app/version.py` — `COMMIT_SHA`, `BUILD_TIME`.
- `backend/app/main.py` — `/health` con i due campi.
- `backend/graph/chat_graph.py` — helper `_usage`, `_merge_usage`, accumulo
  nello stato.
- `backend/services/simplify.py` — usage per chiamata e somma nel merge.
- `backend/app/routes/{chat,simplify}.py` — log dei token.
- `scripts/smoke.py`, `scripts/log_report.py`.
- `backend/tests/test_version.py`, `test_usage.py`, `test_smoke_script.py`,
  `test_log_report.py`.
- `.github/workflows/smoke.yml`.
- `Makefile`, `AGENTS.md`, `README.md`, `runbook.md`.

### Scelte

- **Nessuna dipendenza nuova.** Smoke e report usano la standard library;
  i test caricano gli script con `importlib`.
- **Smoke senza LLM.** Le richieste invalide provano i limiti e l’X-Request-ID
  senza spendere quota.
- **Token, non dollari.** Il free tier può cambiare; il report espone i token
  e applica un prezzo solo se configurato.
- **Log drain esterno, non obbligatorio.** Il codice funziona anche senza:
  il report legge un file esportato. Il drain è una configurazione del
  maintainer, descritta nel runbook.
- **SHA best-effort.** Se Vercel non espone `VERCEL_GIT_COMMIT_SHA` nel
  container, `/health` dice `unknown`; `--require-commit` rende il check
  fallibile quando il maintainer vuole imporlo.

## Criteri di accettazione

1. `cd backend && uv run pytest -q tests/test_version.py tests/test_usage.py tests/test_smoke_script.py tests/test_log_report.py` verde.
2. `make test` verde.
3. `make check` verde.
4. `python3 scripts/smoke.py --base-url http://127.0.0.1:8000` funziona
   contro il backend locale (422 e X-Request-ID).
5. `python3 scripts/smoke.py` contro produzione: `health.commit` valorizzato
   o warning esplicito; tutti i check verdi.
6. `scripts/log_report.py` su un campione produce p50/p95, 429 e token.
7. Workflow `smoke.yml` presente e valido.

## Rischi

| Rischio | Mitigazione |
|---|---|
| `VERCEL_GIT_COMMIT_SHA` non disponibile nel container | Fallback `unknown`; `--require-commit` opzionale; runbook con `BUILD_TIME` |
| Log drain non configurato | Il report funziona su file; il runbook spiega il drain |
| Usage assente da alcuni modelli | Campi a 0; il report mostra quanti eventi non hanno usage |
| Smoke test colpisce la produzione e consuma quota | Solo richieste 422, nessuna chiamata valida |
| Falso positivo del report su log parziali | Il report stampa il numero di eventi e i campi mancanti |

## Rollback

Revertire il branch. Nessuna migrazione. Il deploy Production resta manuale e
lo smoke test è un comando separato.

# Runbook — deploy, smoke test e osservabilità

## Deploy Production

Il deploy non parte dal push su `main`. È manuale e richiede autorizzazione.

```bash
git status                      # pulito
git log --oneline -1            # commit atteso
make check                      # test + lint + build + process check
vercel --prod                   # deploy Production
make smoke                      # verifica reale, senza chiamate LLM valide
```

Confronta `GET /health` con il commit:

```bash
curl -sS https://farmaco-chiaro.vercel.app/health
git rev-parse --short HEAD
```

Se `commit` è `unknown`, Vercel non sta esponendo `VERCEL_GIT_COMMIT_SHA` al
container. Imposta `BUILD_TIME` nelle env del progetto e verifica la
documentazione Vercel per lo SHA; nel frattempo lo smoke test resta
funzionante e segnala un warning.

## Smoke test

```bash
make smoke
# oppure
python3 scripts/smoke.py --base-url https://farmaco-chiaro.vercel.app
python3 scripts/smoke.py --require-commit
```

Controlla: `/health`, `/api/rag/status`, `/api/farmaco/{id}`, la pagina
farmaco, `X-Request-ID`, `422` su messaggio vuoto e su messaggio di 1.001
caratteri. Non fa mai una chiamata valida all'LLM.

Il workflow `Production smoke` lo esegue ogni giorno alle 06:00 UTC e su
`workflow_dispatch`. Quando `/health` espone lo SHA in modo stabile, aggiungi
`--require-commit` al workflow.

## Log drain

1. Vercel → progetto `farmaco-chiaro` → Settings → Log Drains.
2. Aggiungi un drain verso Better Stack (free tier) o un endpoint HTTP che
   accetti JSON.
3. Seleziona i log runtime, non quelli di build.
4. Fai una richiesta alla demo e verifica che arrivi un evento
   `"event":"http_request"`.
5. Esporta i log in JSONL dal servizio scelto, oppure usa
   `vercel logs <deployment> --json > logs.jsonl` per un campione.

Il codice non dipende dal drain: senza drain il report funziona su un file
esportato.

## Report

```bash
make report-logs LOGS=logs.jsonl
python3 scripts/log_report.py logs.jsonl --json
```

Soglie consigliate per la demo:

```bash
python3 scripts/log_report.py logs.jsonl \
  --max-tokens 2000000 \
  --max-errors 0 \
  --max-429 50
```

- `--max-tokens` è il budget mensile in token; il free tier può cambiare, quindi
  la soglia va rivista.
- `--max-errors 0` fallisce su qualunque 5xx.
- `--max-429` distingue un picco di abuso da un utente che ha superato il
  limite.
- Per una stima in dollari aggiungi `--usd-per-1m-input` e
  `--usd-per-1m-output` con il prezzo corrente del modello.

Esegui il report una volta a settimana e conserva il JSON come record.

## Alert

Configura nel servizio di log un alert quando:

- compaiono 5xx;
- il rapporto `429 / richieste` supera il 10% in un'ora;
- i token del mese superano la soglia.

Destinatario: il maintainer. Non c'è un on-call in questa fase.

## Se lo smoke test fallisce

| Check | Cosa significa | Azione |
|---|---|---|
| `health` | il backend non risponde o non è healthy | `vercel ls`, ispeziona il deployment, rollback |
| `rag_status` | dataset mancante | verifica `backend/data/rag/` nel deployment |
| `farmaco_api` / `farmaco_page` | route o proxy rotti | controlla i log del deployment |
| `request_id` | manca il middleware | il deployment non è quello atteso: confronta lo SHA |
| `chat_vuoto` / `chat_lungo` | il backend accetta input non limitati | deployment vecchio o hardening rimosso: rollback o redeploy |
| Qdrant `available: false` | warning, non errore | il fallback BM25 è voluto; indaga se persiste |

Rollback: `vercel rollback` o promuovi il deployment precedente dalla
dashboard, poi `make smoke` di nuovo.

## Sicurezza

- I log contengono `client_hash`, mai l'IP in chiaro né il testo dei messaggi.
- Non caricare file di log con dati personali in repository o artifact pubblici.
- Le chiavi restano nelle env di Vercel, non nel repository.

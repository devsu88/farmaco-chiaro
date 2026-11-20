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

Confronta `GET /api/health` con il commit:

```bash
curl -sS https://farmaco-chiaro.vercel.app/api/health
git rev-parse --short HEAD
```

Se `commit` è `unknown`, Vercel non sta esponendo `VERCEL_GIT_COMMIT_SHA` al
container. Imposta `BUILD_TIME` nelle env del progetto e verifica la
documentazione Vercel per lo SHA; nel frattempo lo smoke test resta
funzionante e segnala un warning. Verificato il 2026-11-20: Vercel espone lo
SHA, quindi `commit` corrisponde a `HEAD`; `built_at` resta `unknown` finché
non si imposta `BUILD_TIME`. Lo SHA è il campo autorevole.

## Smoke test

```bash
make smoke
# oppure
python3 scripts/smoke.py --base-url https://farmaco-chiaro.vercel.app
python3 scripts/smoke.py --require-commit
```

Controlla: `/api/health`, `/api/rag/status`, `/api/farmaco/{id}`, la pagina
farmaco, `X-Request-ID`, `422` su messaggio vuoto e su messaggio di 1.001
caratteri. Non fa mai una chiamata valida all'LLM.

Il workflow `Production smoke` lo esegue ogni giorno alle 06:00 UTC e su
`workflow_dispatch`. Quando `/health` espone lo SHA in modo stabile, aggiungi
`--require-commit` al workflow.

## Log: percorso Hobby (attuale)

Vercel conserva i log runtime per **un'ora** sul piano Hobby e i Log Drains
richiedono Pro. Il percorso attuale è un export periodico:

```bash
# ultima finestra, in un file pronto per il report
make export-logs EXPORT_ARGS="--since 50m --output logs.jsonl --append"

# oppure solo su stdout
make export-logs
```

`scripts/export_logs.py` chiama `vercel logs --json`, scompatta il record
Vercel, tiene solo i nostri eventi e deduplica la sovrapposizione tra due
export. Richiede `vercel login` in locale o `VERCEL_TOKEN` in CI.

Il workflow `Log export` gira ogni 30 minuti con finestra di 50 minuti,
esegue il report (`--max-errors 0`) e conserva `logs.jsonl` come artifact per
30 giorni. Per una vista più lunga scarica gli artifact e concatenali:

```bash
gh run download --pattern 'logs-*' -D artifacts
cat artifacts/*/logs.jsonl > logs-settimana.jsonl
make report-logs LOGS=logs-settimana.jsonl
```

Limiti onesti: è polling, non streaming. Se GitHub salta le esecuzioni per più
di un'ora, quella finestra è persa; non ci sono alert in tempo reale, solo il
fallimento del job. Per la demo basta.

## Log drain (richiede Pro)

Se il progetto passa a Pro, il drain sostituisce l'export:

1. Vercel → progetto → Settings → Drains → Logs.
2. Endpoint verso Better Stack (free tier) o un endpoint HTTP tuo.
3. Solo log runtime, non build.
4. Verifica: fai una richiesta alla demo e cerca un evento
   `"event":"http_request"` nel servizio.
5. Poi puoi rimuovere il workflow `Log export`.

Il drain è streaming e conserva lo storico fuori da Vercel; l'export resta
utile come fallback.

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

Su Hobby l'unico alert è il fallimento del workflow `Log export` (5xx nella
finestra). Con un drain Pro puoi configurare nel servizio di log un alert
quando:

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

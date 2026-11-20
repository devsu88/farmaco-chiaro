# Spec: contenere costo e abuso degli endpoint LLM

Data: 2026-11-20. Deriva da `intent.md` nella stessa cartella, con le
decisioni del 2026-11-20.

## Obiettivo

Mettere un confine esplicito e verificabile su ciò che un client può far
spendere al servizio, senza cambiare il comportamento normale di chat,
semplificazione e TTS. Nessuna autenticazione, nessun nuovo servizio.

## Requisiti

### R1 — Limiti di input

| Campo | Limite |
|---|---|
| `ChatRequest.messaggio` | 1–1.000 caratteri, spazi esterni rimossi, vuoto rifiutato |
| `ChatRequest.storico` | massimo 10 elementi |
| `ChatMessage.testo` | massimo 2.000 caratteri |
| `ChatMessage.ruolo` / `ChatRequest.sessione_id` / `farmaco_id` | massimo 64 caratteri |
| `SimplifyRequest.testo` | massimo 12.000 caratteri (se presente) |
| `SimplifyRequest.sezione` | massimo 80 caratteri |
| `Search q` | massimo 200 caratteri |
| `ScenarioRequest.farmaco_id` | massimo 64 caratteri |

I limiti sono configurabili da ambiente con i default qui sopra. Una richiesta
fuori limite restituisce `422` con il formato di validazione FastAPI.

### R2 — Rate limit

- Bucket: `chat` = 20 req/min, `simplify` = 20 req/min, `tts` = 10 req/min,
  finestra 60 s. Configurabili con `RATE_LIMIT_CHAT`, `RATE_LIMIT_SIMPLIFY`,
  `RATE_LIMIT_TTS`, `RATE_LIMIT_WINDOW_SECONDS`.
- Chiave: `bucket + IP client`. L'IP è il primo valore di `X-Forwarded-For`,
  altrimenti `request.client.host`. Il proxy Next inoltra l'header del browser.
- Implementazione: sliding window in memoria, thread-safe, con pulizia
  periodica delle chiavi vuote. Vale **per istanza**: su più istanze il limite
  effettivo è la somma. È accettato e documentato.
- Risposta al superamento: `429`, header `Retry-After` in secondi interi,
  messaggio utente “Troppe richieste. Riprova tra qualche secondo.”.
- Il controllo avviene prima della logica della route, tramite dependency
  FastAPI. Un `Content-Length` oltre `MAX_REQUEST_BYTES` (default 2 MB)
  restituisce `413` prima di leggere il corpo.

### R3 — Timeout del proxy

`frontend/src/lib/backend.ts` applica `AbortSignal.timeout` a ogni chiamata al
backend. Default `PROXY_TIMEOUT_MS = 100000` (100 s), sopra il timeout LLM di
90 s. Allo scadere restituisce `504` con:

```json
{ "error": { "code": "BACKEND_TIMEOUT", "message": "Il servizio sta impiegando troppo tempo. Riprova." } }
```

Il proxy inoltra al backend `x-forwarded-for` (dal browser) e restituisce al
client `retry-after` e `x-request-id`.

### R4 — Log strutturati

Ogni richiesta a `/api/chat`, `/api/simplify`, `/api/tts` o con status ≥ 500
produce una riga JSON su stdout:

```json
{"event":"http_request","request_id":"...","method":"POST","path":"/api/chat","status":200,"duration_ms":842.1,"client_hash":"..."}
```

Campi: `event`, `request_id`, `method`, `path`, `status`, `duration_ms`,
`client_hash` (SHA-256 troncato, mai l'IP in chiaro). Le route aggiungono:

- `chat_completed`: `farmaco_id`, `fonti`, `fallback_usato`, `model`;
- `simplify_completed`: `farmaco_id`, `sezione`, `cached`, `errore`;
- `tts_completed`: `chars`, `voce`;
- `rate_limited`: `bucket`, `retry_after`.

Nessun contenuto del messaggio, del testo o della risposta finisce nei log.
Ogni risposta ha `X-Request-ID`.

### R5 — UX del client

- `ChatPanel` limita l'input a 1.000 caratteri e invia solo gli ultimi 10 turni.
- Gli errori del server sono mostrati all'utente quando sono stringhe; un
  `422` mostra “Dati non validi” invece dell'array di validazione.
- Il messaggio di `429` è quello restituito dal backend.

### R6 — Test

- Unit test dello sliding window: soglia, `Retry-After`, chiavi separate,
  scadenza della finestra.
- API test: `429` al secondo invio con limite forzato a 1; `422` per messaggio
  lungo, storico oltre 10, testo di semplificazione oltre 12.000; `X-Request-ID`
  presente; log JSON parsabile per una richiesta chat.
- I test esistenti restano verdi; il limiter viene azzerato tra i test.

## Design

### File

- `backend/app/config.py` — nuovi limiti da ambiente.
- `backend/app/schemas.py` — `Field` con `min_length`/`max_length`, validatore
  per il messaggio.
- `backend/app/rate_limit.py` — `Limit`, `SlidingWindowLimiter`,
  `client_ip`, `rate_limit(bucket)`.
- `backend/app/observability.py` — `RequestLogMiddleware`, `log_event`.
- `backend/app/main.py` — middleware e ordine CORS.
- `backend/app/routes/{chat,simplify,tts}.py` — dependency e log di dominio.
- `backend/tests/test_rate_limit.py`, `backend/tests/test_observability.py`,
  `backend/tests/test_api_limits.py`; fixture di reset in `conftest.py`.
- `frontend/src/lib/backend.ts` — timeout, header, errori.
- `frontend/src/lib/api.ts` — parsing errori.
- `frontend/src/components/ChatPanel.tsx` — `maxLength`, storico limitato,
  messaggio d'errore.

### Scelte

- **Dependency, non middleware, per il rate limit.** La dependency ha accesso
  a `Request`, può restituire `HTTPException` con header e si testa senza
  costruire un'app separata.
- **In memoria, non Redis.** Il vincolo è non aggiungere dipendenze runtime.
  Il limite per istanza è scritto nella spec e nell'intent; sarà rivisto se il
  traffico cresce.
- **Log come messaggio JSON.** Non si aggiunge un formatter globale: il logger
  esistente stampa già timestamp e livello, e il payload resta parsabile.
- **`X-Forwarded-For` inoltrato dal proxy.** Senza questo, il backend vedrebbe
  solo l'IP del server Next e il limite diventerebbe globale. Il primo valore
  è best-effort: Vercel lo imposta, ma un client che chiama il backend
  direttamente potrebbe falsificarlo. Il backend è raggiungibile solo dal
  servizio frontend in produzione.

## Criteri di accettazione

1. `cd backend && uv run pytest -q tests/test_rate_limit.py tests/test_observability.py tests/test_api_limits.py` verde.
2. `make test` verde (174 test esistenti + nuovi).
3. `make build` verde.
4. `python3 scripts/check_ai_native.py` verde.
5. `grep -R "max_length" backend/app/schemas.py` mostra i limiti di R1.
6. `curl -i` su `/api/chat` due volte con limite forzato mostra `429` e
   `Retry-After` (verificato nei test).
7. Nessuna chiamata reale a OpenRouter nei test.

## Rischi

| Rischio | Mitigazione |
|---|---|
| Limite per istanza inefficace su più istanze | Documentato; se serve, store condiviso in una spec successiva |
| IP falsificabile | Backend privato dietro il servizio frontend; il proxy inoltra l'header |
| Soglie troppo basse per un utente reale | 20/min è sopra l'uso umano; TTS 10/min copre 3–5 chunk |
| `AbortSignal.timeout` non disponibile | Node 20+ richiesto da Next 16; build CI lo verifica |
| Log con dati personali | Solo hash dell'IP; nessun contenuto |
| Test flaky per stato globale del limiter | Fixture autouse di reset in `conftest.py` |

## Rollback

Revertire il branch. Non ci sono migrazioni né dati modificati. Le variabili
d'ambiente nuove hanno default sicuri, quindi un deploy senza configurarle
funziona.

## Risultato (2026-11-20)

Implementato e verificato sul branch `feat/llm-endpoint-hardening`:

- `make test` → 191 passed.
- `make build` → verde.
- `make check` → verde, checker `OK`.
- Limiti, `429` con `Retry-After`, `413`, `422`, `X-Request-ID` e log JSON
  coperti da test; nessuna chiamata al provider nei test.

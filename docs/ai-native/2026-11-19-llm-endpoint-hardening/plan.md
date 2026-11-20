# Plan: contenere costo e abuso degli endpoint LLM

Deriva da `spec.md` nella stessa cartella. Esecuzione nativa sul branch
`feat/llm-endpoint-hardening`.

**Goal:** limiti di input, rate limit, timeout del proxy e log strutturati
senza cambiare il comportamento normale.

**Architecture:** dependency FastAPI per il rate limit, middleware per request
id e log, `Field` Pydantic per i limiti, `AbortSignal.timeout` nel proxy Next.

**Tech stack:** Python 3.13, FastAPI, Pydantic v2, pytest, Next.js 16.

## Task

### Task 1 — Test dei limiti di input (prima del codice)

**File:** `backend/tests/test_api_limits.py` (nuovo).

- [x] Scrivere i test: messaggio > 1.000 → 422; storico > 10 → 422; testo
  simplify > 12.000 → 422; messaggio di soli spazi → 422; richiesta normale →
  200/404 atteso.
- [x] Eseguire e verificare che falliscano per il motivo giusto.

### Task 2 — Limiti in config e schemi

**File:** `backend/app/config.py`, `backend/app/schemas.py`.

- [x] Aggiungere le costanti da ambiente con i default della spec.
- [x] Applicare `Field` e il validatore del messaggio.
- [x] Eseguire i test del Task 1: verdi.

### Task 3 — Sliding window

**File:** `backend/app/rate_limit.py` (nuovo), `backend/tests/test_rate_limit.py` (nuovo).

- [x] Scrivere i test unit: N consentite, N+1 rifiutata, `Retry-After` ≥ 1,
  chiavi separate, reset dopo la finestra.
- [x] Implementare `Limit`, `SlidingWindowLimiter` (clock iniettabile, lock,
  pulizia), `client_ip`, `rate_limit(bucket)`.
- [x] Eseguire: verdi.

### Task 4 — Osservabilità

**File:** `backend/app/observability.py` (nuovo), `backend/app/main.py`, `backend/tests/test_observability.py` (nuovo).

- [x] Middleware che assegna `X-Request-ID`, misura la durata e logga JSON per
  gli endpoint caldi e per gli errori ≥ 500.
- [x] `log_event` con `request_id` e `client_hash`.
- [x] Test: header presente; log parsabile; nessun contenuto del messaggio.
- [x] Eseguire: verdi.

### Task 5 — Integrazione nelle route

**File:** `backend/app/routes/chat.py`, `simplify.py`, `tts.py`, `backend/tests/test_api_limits.py`.

- [x] Dependency `rate_limit("chat"|"simplify"|"tts")`.
- [x] Log di dominio `chat_completed`, `simplify_completed`, `tts_completed`.
- [x] Test `429` con limite forzato a 1 e `Retry-After`; reset del limiter tra
  i test in `conftest.py`.
- [x] Eseguire: verdi.

### Task 6 — Proxy e UI

**File:** `frontend/src/lib/backend.ts`, `frontend/src/lib/api.ts`,
`frontend/src/components/ChatPanel.tsx`, route proxy di chat/simplify/tts.

- [x] Timeout 100 s con `AbortSignal.timeout`; `504` `BACKEND_TIMEOUT`.
- [x] Inoltrare `x-forwarded-for`; restituire `retry-after` e `x-request-id`.
- [x] `fetchJSON`: dettaglio stringa o “Dati non validi”.
- [x] Chat: `maxLength=1000`, ultimi 10 turni, messaggio d'errore del server.
- [x] `npm run lint` e `npm run build`.

### Task 7 — Documentazione operativa

**File:** `backend/.env.example`, `AGENTS.md`, `docs/ai-native/2026-11-19-llm-endpoint-hardening/plan.md`.

- [x] Documentare le variabili nuove e il comportamento per istanza.
- [x] Aggiornare lo stato del piano.
- [x] `python3 scripts/check_ai_native.py`.

### Task 8 — Verifica e merge

- [x] `make test`
- [x] `make build`
- [x] `make check`
- [x] `git diff --stat`; nessuna modifica non prevista.
- [x] Merge fast-forward in `main` e push.

## Rischi

| Rischio | Mitigazione |
|---|---|
| Il limiter globale rende i test dipendenti dall'ordine | Fixture autouse di reset |
| `BaseHTTPMiddleware` interferisce con lo streaming audio | Test TTS esistenti + verifica manuale del file WAV |
| `Retry-After` non arriva al browser | Header inoltrato dal proxy e testato sul backend |
| Il limite per IP dietro proxy è globale | `x-forwarded-for` inoltrato dalle route calde |

## Prove

| Comando | Atteso |
|---|---|
| `uv run pytest -q tests/test_rate_limit.py` | verdi |
| `uv run pytest -q tests/test_observability.py` | verdi |
| `uv run pytest -q tests/test_api_limits.py` | verdi |
| `make test` | 174 + nuovi verdi |
| `make build` | build verde |
| `make check` | tutto verde + checker `OK` |

## Risultato (2026-11-20)

- `make test`: **191 passed** (174 esistenti + 17 nuovi).
- `make build`: verde, 17 route.
- `python3 scripts/check_ai_native.py`: `OK` — 2 iniziative, 176 file
  tracciati puliti, 621 farmaci.
- Nessuna chiamata reale a OpenRouter nei test.
- Nuovi file: `backend/app/rate_limit.py`, `backend/app/observability.py`,
  `backend/tests/test_rate_limit.py`, `backend/tests/test_observability.py`,
  `backend/tests/test_api_limits.py`.
- File modificati: `backend/app/{config,schemas,main}.py`, route
  `chat/simplify/tts/search`, `frontend/src/lib/{backend,api}.ts`,
  `frontend/src/components/ChatPanel.tsx`, `frontend/src/hooks/useTTS.ts`,
  le tre route proxy, `backend/.env.example`, `AGENTS.md`.

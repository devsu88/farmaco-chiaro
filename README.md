# Farmaco Chiaro

Fogli illustrativi AIFA leggibili: originale a sinistra, versione ETR a destra,
chatbot con citazioni verificabili.

Il report completo del progetto è in [`REPORT.md`](./REPORT.md).

## Struttura

```
backend/    FastAPI + LangGraph, gestito con uv
frontend/   Next.js 16 + React 19 + Tailwind
infra/      (predisposto per deploy)
```

## Avvio rapido

### Backend

```bash
cd backend
cp .env.example .env        # inserire OPENROUTER_API_KEY
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Aprire `http://localhost:3000`.

### Docker Compose

```bash
cp backend/.env.example backend/.env   # inserire OPENROUTER_API_KEY
docker compose up --build
```

## Comandi utili

```bash
make index   # rigenera backend/index/blocchi.json
make ingest  # rigenera l'indice vettoriale ChromaDB (richiede API key)
make test    # pytest + eslint
make build   # next build
make dev     # backend + frontend in parallelo
```

## Retrieval

Il chatbot usa un retrieval ibrido: BM25 + embeddings
(`nvidia/nemotron-3-embed-1b:free`) in ChromaDB, con fusione RRF.

L'ingestion è volutamente separata dall'app:

```bash
cd backend
uv run python index/build_index.py
uv run python scripts/ingest_vector_index.py --reset
```

Se `backend/index/chroma/` non esiste, o se l'embedding fallisce, il backend
usa automaticamente il solo BM25. Per forzare il lessicale:

```env
RETRIEVAL_MODE=bm25
```

## Dati

- `backend/data/farmaci.json`: registro unico `id -> file markdown / documento`.
- `backend/data/catalogo_farmaci.json`: preview per le card della home.
- `backend/data/markdown/FI/*.md`: fonte di conoscenza per chat e documento originale.
- `backend/index/blocchi.json`: indice generato, con `index_meta.json`.
- `backend/index/chroma/`: indice vettoriale ChromaDB generato dallo script di ingestion (ignorato da Git).
- `backend/data/cache/`: cache runtime di semplificazioni e audio TTS (ignorata da Git).

Dopo aver modificato i markdown:

```bash
make index
```

La CI verifica che l'indice committato sia aggiornato con
`uv run python index/build_index.py --check`.

## API principali

| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/health` | liveness |
| GET | `/ready` | readiness (registro + indice) |
| GET | `/api/farmaci` | lista preview |
| GET | `/api/farmaci/{id}` | dettaglio preview |
| GET | `/api/farmaci/{id}/documento` | documento citabile a blocchi |
| GET | `/api/search?q=` | ricerca per farmaco |
| POST | `/api/simplify` | semplificazione ETR (con cache persistente) |
| POST | `/api/tts` | sintesi vocale della versione facile |
| POST | `/api/chat` | chat con fonti verificate |

Il browser chiama sempre le route proxy same-origin di Next (`/api/*`), che
inoltrano le richieste al backend tramite `BACKEND_URL`.

## Note di sicurezza

- `.env` è ignorato da Git.
- La chiave OpenRouter resta solo nel backend.
- Le citazioni della chat vengono validate contro i blocchi dell'indice.
- Il retrieval riconosce intenti comuni (gravidanza, allattamento, bambini, dosaggio, condivisione del farmaco anche con familiari), sinonimi clinici e la chat usa lo storico per riscrivere i follow-up.
- Il retrieval è ibrido: BM25 + embeddings ChromaDB con fusione RRF; senza indice vettoriale torna a BM25.
- Le risposte che uniscono più informazioni ricevono automaticamente le fonti corrispondenti.
- Le domande sulla conversazione ("ti ho già chiesto...") vengono risposte dallo storico, senza retrieval.
- Le citazioni vengono ridotte alla frase pertinente e filtrate rispetto alla risposta.
- La sintesi vocale usa OpenRouter TTS (`TTS_MODEL`, `TTS_VOICE`) e non le voci del browser.
- Il testo viene riprodotto in chunk da ~600 caratteri: la prima frase parte subito e le risposte restano leggere.
- La versione facile mostra solo l'essenziale (max 7 frasi); i dettagli si approfondiscono con la chat.
- Le semplificazioni e gli audio sono in cache su disco; `forza: true` rigenera la semplificazione.

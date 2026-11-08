# Farmaco Chiaro

**Farmaco Chiaro** rende leggibili i fogli illustrativi AIFA. Il documento originale
resta sempre visibile; accanto, l'utente può leggere una versione in linguaggio
semplice e fare domande a un chatbot che cita il paragrafo da cui proviene la
risposta.

L'applicazione non formula diagnosi e non sostituisce il medico o il farmacista.
Aiuta a capire un testo lungo e a preparare le domande da porre a un professionista.

## Demo

Prova l'app online: **https://farmaco-chiaro.vercel.app**

[![Farmaco Chiaro su Vercel](docs/vercel-demo.png)](https://farmaco-chiaro.vercel.app)

## Funzionalità

- **Documento originale integrale**, suddiviso in blocchi citabili e sempre consultabile.
- **Versione semplificata su richiesta**: frase di sintesi, punti chiave, glossario
  dei termini difficili e domande da fare al farmacista.
- **Chat con fonti verificabili**: ogni risposta riporta i blocchi usati e un click
  evidenzia il paragrafo corrispondente nel documento originale.
- **Sintesi vocale** della versione semplificata.
- **Ricerca per nome, principio attivo o sintomo**.

## Come funziona

1. I markdown dei fogli AIFA vengono suddivisi in blocchi citabili
   (`backend/index/blocchi.json`).
2. Lo script di ingestion calcola gli embedding dei blocchi e li salva in ChromaDB.
3. La ricerca combina BM25 e ricerca vettoriale, fonde i risultati con Reciprocal
   Rank Fusion e seleziona i passaggi più pertinenti.
4. Un LLM su OpenRouter genera la risposta e la versione semplificata a partire dai
   passaggi recuperati.
5. Se l'indice vettoriale o gli embedding non sono disponibili, il retrieval
   prosegue in modalità BM25 e la chat resta operativa.

## Architettura

| Componente | Tecnologia | Ruolo |
|---|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS | Interfaccia utente e proxy same-origin verso il backend |
| Backend | FastAPI, LangGraph | API REST e orchestrazione della chat |
| Retrieval | ChromaDB, BM25, RRF | Ricerca semantica e lessicale sui blocchi |
| LLM e servizi AI | OpenRouter | Chat, semplificazione, embeddings e sintesi vocale |
| Dati | JSON e markdown AIFA | Catalogo, blocchi e testi di partenza |

```text
.
├── backend/
│   ├── app/            # FastAPI: route, schemi, configurazione
│   ├── graph/          # grafo LangGraph della chat
│   ├── services/       # retrieval, semplificazione, citazioni, TTS
│   ├── data/           # catalogo e markdown dei fogli illustrativi
│   ├── index/          # blocchi citabili e indice ChromaDB
│   └── scripts/        # ingestion dell'indice vettoriale
├── frontend/           # Next.js App Router
├── docs/               # screenshot della demo
├── docker-compose.yml
└── vercel.json         # deploy su Vercel Services
```

## Requisiti

- Python 3.13 e [uv](https://docs.astral.sh/uv/)
- Node.js 20 o superiore
- API key [OpenRouter](https://openrouter.ai/)

## Avvio rapido

```bash
# Backend
cd backend
cp .env.example .env        # inserire OPENROUTER_API_KEY
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend (in un altro terminale)
cd frontend
npm install
npm run dev
```

Aprire `http://localhost:3000`. Il frontend inoltra le chiamate a `/api/*` verso il
backend, quindi il browser resta sullo stesso origin.

### Docker Compose

```bash
cp backend/.env.example backend/.env   # inserire OPENROUTER_API_KEY
docker compose up --build
```

## Configurazione

Le variabili sono documentate in `backend/.env.example`. Le principali:

| Variabile | Default | Descrizione |
|---|---|---|
| `OPENROUTER_API_KEY` | nessuno | Chiave per LLM, embeddings e TTS |
| `CHAT_MODEL` | `nvidia/nemotron-3-ultra-550b-a55b:free` | Modello della chat |
| `SIMPLIFY_MODEL` | `nvidia/nemotron-3-ultra-550b-a55b:free` | Modello della semplificazione |
| `RETRIEVAL_MODE` | `hybrid` | `hybrid` usa BM25 e ChromaDB, `bm25` solo la ricerca lessicale |
| `EMBEDDING_MODEL` | `nvidia/nemotron-3-embed-1b:free` | Modello usato per l'indice vettoriale |
| `CHROMA_COLLECTION` | `farmaci_blocchi` | Collezione ChromaDB |
| `CHROMA_DIR` | `backend/index/chroma` | Directory dell'indice; su Vercel diventa `/tmp/chroma` |
| `FRONTEND_ORIGINS` | `http://localhost:3000` | Origini CORS ammesse, separate da virgola |

`EMBEDDING_MODEL` deve restare allineato al modello usato per costruire l'indice.
Se cambia, rigenerare l'indice con `make ingest`.

## Comandi

| Comando | Descrizione |
|---|---|
| `make dev` | Avvia backend e frontend in parallelo |
| `make index` | Rigenera i blocchi citabili dai markdown |
| `make ingest` | Rigenera l'indice vettoriale su ChromaDB (richiede API key) |
| `make test` | Test backend e lint frontend |
| `make lint` | Ruff sul backend ed ESLint sul frontend |
| `make build` | Build di produzione del frontend |
| `make up` / `make down` | Avvia o ferma Docker Compose |

Dopo aver modificato i markdown servono `make index` e `make ingest`, poi il
riavvio del backend.

## Test

```bash
make test
```

I test del backend usano `pytest`; il frontend viene verificato con ESLint.

## Deploy

Il deploy di produzione usa **Vercel Services** con due servizi:

- `frontend`: applicazione Next.js.
- `backend`: container FastAPI, raggiungibile dal frontend tramite il binding
  privato `BACKEND_URL`.

La configurazione è in `vercel.json`. Sul filesystem read-only di Vercel, ChromaDB
copia l'indice incluso nel deploy in `/tmp/chroma` al primo utilizzo.

Con `vercel deploy` l'indice viene caricato perché presente nel progetto locale. Un
deploy automatico da Git richiede che `backend/index/chroma` sia committato oppure
rigenerato in CI, altrimenti il retrieval resta in modalità BM25.

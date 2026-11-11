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
- **Percorso guidato "Una cosa alla volta"**: quattro schermate semplici, recuperate
  con ricerca semantica e citate dal foglio, con audio e modalità alto contrasto.
- **"Cosa faccio se…?"**: risposte brevi e citate per dimenticanza, dose doppia,
  reazione avversa e alcol.
- **Scheda condivisibile con QR e WhatsApp** per familiari e caregiver.
- **Versione semplificata su richiesta**: frase di sintesi, punti chiave, glossario
  dei termini difficili e domande da fare al farmacista.
- **Chat con fonti verificabili**: ogni risposta riporta i blocchi usati e un click
  evidenzia il paragrafo corrispondente nel documento originale.
- **Sintesi vocale** della versione semplificata.
- **Ricerca per nome, principio attivo o sintomo**.

## Come funziona

1. I PDF dei fogli AIFA vengono convertiti in Markdown e suddivisi in chunk e
   blocchi citabili (`backend/data/rag/`).
2. La pipeline `aifa_rag` calcola gli embedding dei chunk e li carica su Qdrant
   (Cloud o server locale), con cache su disco riprendibile.
3. La ricerca combina BM25 e ricerca vettoriale, fonde i risultati con Reciprocal
   Rank Fusion e seleziona i passaggi più pertinenti.
4. Un LLM su OpenRouter genera la risposta e la versione semplificata a partire dai
   passaggi recuperati.
5. Guida, chat e scenari usano la ricerca semantica su Qdrant; la home combina
   parole chiave e semantica. Se Qdrant o gli embedding non sono disponibili,
   il retrieval prosegue in BM25 e l'app resta operativa.

## Architettura

| Componente | Tecnologia | Ruolo |
|---|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS | Interfaccia utente e proxy same-origin verso il backend |
| Backend | FastAPI, LangGraph | API REST e orchestrazione della chat |
| Retrieval | Qdrant, BM25, RRF | Semantica per guida/chat/scenari, keyword + semantica in home |
| LLM e servizi AI | OpenRouter | Chat, semplificazione, embeddings e sintesi vocale |
| Dati | JSON AIFA | Registro, chunk e blocchi citabili di 621 fogli illustrativi |

```text
.
├── backend/
│   ├── app/            # FastAPI: route, schemi, configurazione
│   ├── aifa_rag/       # pipeline dataset, embedding e indice Qdrant
│   ├── graph/          # grafo LangGraph della chat
│   ├── services/       # retrieval, semplificazione, citazioni, TTS
│   ├── eval/           # domande di valutazione del retrieval
│   └── data/rag/       # chunk, sezioni, blocchi e registro (runtime)
├── frontend/           # Next.js App Router
├── docs/               # screenshot della demo
├── docker-compose.yml  # frontend + backend + Qdrant locale
└── vercel.json         # deploy su Vercel Services, redirect e cron
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
docker compose up -d qdrant
# Indicizza sul Qdrant locale (una volta sola, o dopo aver rigenerato il dataset)
cd backend && QDRANT_URL=http://localhost:6333 uv run python -m aifa_rag.cli index
cd .. && docker compose up --build
```

## Comandi

| Comando | Descrizione |
|---|---|
| `make dev` | Avvia backend e frontend in parallelo |
| `make dataset` | Rigenera chunk, sezioni, blocchi e registro dai Markdown |
| `make index` | Calcola gli embedding e carica l'indice su Qdrant |
| `make eval` | Valuta il retrieval denso su `backend/eval/qa.jsonl` |
| `make test` | Test backend e lint frontend |
| `make lint` | Ruff sul backend ed ESLint sul frontend |
| `make build` | Build di produzione del frontend |
| `make up` / `make down` | Avvia o ferma Docker Compose |

Dopo aver rigenerato il dataset servono `make index` e il riavvio del backend.
`make index` usa `QDRANT_URL` e `QDRANT_API_KEY` da `backend/.env`.

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

La configurazione è in `vercel.json`. Il container backend include gli artefatti
runtime in `backend/data/rag/`; i vettori vivono su Qdrant Cloud.

Impostare su Vercel le variabili `QDRANT_URL` e `QDRANT_API_KEY` per gli ambienti
Production e Preview. L'indice va caricato una volta da locale:

```bash
cd backend
uv run python -m aifa_rag.cli index
```

Il cron giornaliero `/api/rag/keepalive` evita la sospensione del free tier Qdrant.
Lo stato è visibile su `/api/rag/status`. Se Qdrant non è raggiungibile, il
retrieval continua a funzionare in BM25.

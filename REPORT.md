# Farmaco Chiaro — Report di progetto

> Stato del lavoro al 6 novembre 2026 — demo hackathon

## 1. L'idea

**Farmaco Chiaro** rende leggibili i fogli illustrativi AIFA alle persone che hanno più difficoltà a capirli: anziani, persone con dislessia, afasia o disabilità intellettiva lieve, ma anche chiunque legga un foglietto illustrativo in fretta.

Il problema non è la mancanza di informazioni: il foglietto AIFA è obbligatorio, completo e legalmente vincolante. Il problema è il **linguaggio**. Frasi lunghe, subordinate, termini tecnici, dosaggi sparsi in paragrafi densi. Chi ha bisogno di sapere "quante compresse e ogni quante ore" spesso non riesce a trovarlo.

L'idea è quindi un **traduttore di fogli illustrativi**, non un sostituto del farmacista o del medico:

- **a sinistra** il testo AIFA originale, sempre visibile e integrale;
- **a destra** una versione in linguaggio facile da leggere (ETR — *Easy To Read*), generata solo su richiesta;
- **un chatbot** che risponde a domande sul farmaco citando *documento, sezione, paragrafo e frase esatta*, e che evidenzia quella frase nel testo originale;
- **sintesi vocale** per ascoltare la versione facile.

Principio guida: **non nascondere mai l'originale**. La versione facile è un livello di lettura aggiuntivo, non una riscrittura che sostituisce la fonte.

### Perché questo progetto

- I dati AIFA sono **pubblici** e già disponibili in PDF: nessun problema di licenza o di raccolta dati.
- Non serve OCR: i PDF sono digitali e convertibili in testo.
- Il valore è concentrato su **UX + retrieval con citazioni**, realizzabile da una sola persona in un weekend.
- È un caso d'uso in cui l'LLM è utile ma va **vincolato alla fonte**: un hallucination su un dosaggio è inaccettabile, quindi ogni risposta deve essere ancorata al documento.

## 2. Ambito della demo

La demo copre **5 farmaci** da banco/di uso comune, con 6 sezioni ciascuno:

| id | nome | principio attivo |
|----|------|------------------|
| `tachipirina_1000` | Tachipirina 1000 mg | paracetamolo |
| `aspirina_500` | Aspirina 500 mg | acido acetilsalicilico |
| `augmentin` | Augmentin | amoxicillina / acido clavulanico |
| `moment` | Moment | ibuprofene |
| `plasil` | Plasil | metoclopramide cloridrato |

Sezioni del catalogo JSON: `indicazioni`, `posologia`, `controindicazioni`, `avvertenze`, `effetti_indesiderati`, `scadenza`.

I dati sorgente sono in `../pdf_farmaci/` (PDF, testi estratti, markdown, catalogo). Nel progetto sono stati **copiati** in `backend/data/`, così la demo è autocontenuta e non dipende da percorsi esterni.

## 3. Architettura

Monorepo con due applicazioni separate:

```
farmaco-chiaro/
├── frontend/                 Next.js 16 + React 19 + Tailwind CSS 3
│   └── src/
│       ├── app/              pagine e API route proxy
│       ├── components/       UI (split-screen, chat, TTS)
│       └── lib/api.ts        tipi e client HTTP
├── backend/                  FastAPI + LangGraph, gestito con uv
│   ├── app/                  app FastAPI, route, factory LLM
│   ├── graph/                grafo LangGraph del chatbot
│   ├── tools/                retrieval sui markdown
│   ├── index/                indice dei blocchi + script di build
│   └── data/                 catalogo JSON, markdown, testi, PDF
└── REPORT.md
```

```
┌─────────────────────────────┐
│  Browser (Next.js :3000)    │
│  home → dettaglio → chat    │
└──────────────┬──────────────┘
               │ fetch same-origin
┌──────────────▼──────────────┐
│  Next.js API routes (proxy) │
│  /api/farmaco/[id]          │
│  /api/simplify              │
└──────────────┬──────────────┘
               │ HTTP 127.0.0.1:8000
┌──────────────▼──────────────┐
│  FastAPI (:8000)            │
│  /api/farmaci  /api/search  │
│  /api/simplify /api/chat    │
└──────┬───────────────┬──────┘
       │               │
  catalogo JSON    indice blocchi
  (preview)        + markdown FI
                       │
                 OpenRouter (LLM)
```

### Perché il proxy Next.js

Il browser non chiama mai direttamente il backend. Le API route di Next (`/api/...`) inoltrano le richieste a `127.0.0.1:8000`. Questo evita CORS, problemi di DNS e permette di cambiare l'URL del backend senza toccare il client.

## 4. Il dato: due livelli, due usi

Questa è una scelta architetturale centrale.

| Livello | File | Uso | Chi lo legge |
|---------|------|-----|--------------|
| **Preview** | `data/catalogo_farmaci.json` | schede in home, apertura dettaglio immediata, input della semplificazione | frontend + route `/api/farmaci` + `/api/simplify` |
| **Conoscenza** | `data/markdown/FI/*.md` (5 file, ~17.300 righe) | retrieval del chatbot, citazioni, fallback | indice `blocchi.json` + LangGraph |

Regola: **il JSON non è la fonte per il chatbot**. Il JSON contiene estratti brevi pensati per l'anteprima; il markdown contiene il foglio illustrativo completo ed è l'unica fonte citabile. Così la risposta della chat può citare un paragrafo che nell'anteprima non esiste.

### Indicizzazione

`backend/index/build_index.py` trasforma i markdown in blocchi:

1. **tiene solo il primo foglio** di ogni markdown. I file AIFA contengono più fogli illustrativi concatenati (una formulazione per volta: compresse, gocce, sciroppo, endovenosa…). Indicizzarli tutti faceva pescare al retrieval la formulazione sbagliata.
2. divide per header `##` (sezione) e `###` (sottosezione/paragrafo);
3. pulisce artefatti OCR e righe di pagina;
4. salva per ogni blocco: `id`, `farmaco_id`, `documento`, `sezione`, `paragrafo`, `testo`, `offset_inizio`, `offset_fine`.

Risultato: **92 blocchi** in `backend/index/blocchi.json` (dai 549 iniziali, prima del filtro sul primo foglio).

### Ricerca

`backend/tools/markdown_tool.py` implementa:

- `cerca_testo(query, farmaco_id, limite)` — scoring **BM25 semplificato**: stopword italiane, IDF per far pesare di più i termini rari, saturazione della frequenza, bonus se la query intera compare nel blocco. Restituisce i blocchi ordinati per punteggio.
- `estrai_paragrafo(blocco_id)` — recupero esatto del blocco per la citazione.
- `carica_markdown(farmaco_id)` — caricamento dell'intero foglio (fallback).

La ricerca in home (`/api/search`) usa un keyword matching più semplice sui blocchi e aggrega i punteggi per farmaco. Il "fallback semantico LLM" previsto è ancora uno stub: oggi la ricerca è **solo keyword**. Funziona bene sui nomi e sui sintomi presenti nel testo, ma non coglie sinonimi non indicizzati.

## 5. Backend FastAPI

Avvio: `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`

| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/health` | health check |
| GET | `/api/farmaci` | lista preview (id, nome, principio attivo) |
| GET | `/api/farmaci/{id}` | dettaglio preview dal catalogo JSON |
| GET | `/api/search?q=...` | ricerca keyword sui blocchi, aggregata per farmaco |
| POST | `/api/simplify` | semplificazione ETR di una sezione o di tutte (con cache) |
| POST | `/api/tts` | sintesi vocale della versione facile (HeyGen via OpenRouter) |
| POST | `/api/chat` | chatbot LangGraph con fonti citate |
| GET | `/api/simplify/status` | disponibilità del servizio e modello attivo |

### `POST /api/simplify`

Richiesta:

```json
{ "farmaco_id": "tachipirina_1000", "sezione": "tutta" }
```

oppure, per semplificare un testo arbitrario:

```json
{ "farmaco_id": "tachipirina_1000", "testo": "..." }
```

Comportamento:

- con `sezione: "tutta"` prende dai **blocchi del documento originale** le parti essenziali (`indicazioni`, `posologia`, `controindicazioni`, `avvertenze`), con il catalogo come fallback;
- chiama il modello con un **system prompt ETR sintetico**: massimo 7 frasi, una informazione per frase, voce attiva, dosaggi esatti, nessuna invenzione;
- il prompt dice esplicitamente di **non riassumere tutto il foglio**: la chat serve per approfondire;
- chiede un output JSON con `una_frase`, `versione_facile[]`, `glossario[]`, `domande_farmacista[]`, `entita_verificate`;
- limita l'output a 7 frasi, 3 voci di glossario e 3 domande, anche se il modello ne produce di più;
- salva il risultato in cache persistente su disco (`data/cache/simplify/`); `forza: true` rigenera;
- se la chiave API manca o la risposta non è JSON valido, restituisce un **fallback strutturato** invece di un errore 500.

Il parser JSON è tollerante: rimuove i code fence ` ```json ` e, se necessario, estrae il primo oggetto tra `{` e `}`. In caso di risposta non valida fa un secondo tentativo.

### `POST /api/chat`

Richiesta:

```json
{
  "farmaco_id": "tachipirina_1000",
  "messaggio": "Posso prenderlo se ho il mal di testa?",
  "storico": [{ "ruolo": "utente", "testo": "..." }],
  "sessione_id": "opzionale"
}
```

Risposta:

```json
{
  "risposta": "...",
  "fonti": [
    {
      "documento": "Foglio illustrativo Tachipirina 1000 mg – AIFA",
      "sezione": "Che cos'è Tachipirina e a cosa serve",
      "paragrafo": "1",
      "testo_evidenziato": "span esatto citato"
    }
  ],
  "sessione_id": "default",
  "fallback_usato": false
}
```

## 6. Il chatbot LangGraph

Il grafo è in `backend/graph/chat_graph.py`, compilato con `MemorySaver` (memoria in RAM, nessun database).

```
ricevi → query_expansion → retrieval → rerank → estrai → genera ─┬→ output → END
                                                                  └→ fallback → output → END
```

| Nodo | Cosa fa |
|------|---------|
| `ricevi` | normalizza lo stato iniziale |
| `query_expansion` | l'LLM riscrive la domanda con sinonimi e termini tecnici ("mal di testa" → "cefalea, dolore testa, dosaggio pediatrico") |
| `retrieval` | `cerca_testo` BM25 sul farmaco selezionato, top 5 blocchi |
| `rerank` | l'LLM sceglie il blocco più pertinente; se non risponde o risponde male, si usa comunque il **miglior candidato** del retrieval (best effort) |
| `estrai` | recupera il testo esatto del blocco per la citazione |
| `genera` | costruisce il contesto con i **3 blocchi migliori** e chiede una risposta JSON con fonti |
| `fallback` | se il retrieval non trova nulla, carica l'intero markdown e genera comunque una risposta |
| `output` | prepara il risultato per l'API |

Regole nel system prompt: rispondere **solo** con il contesto fornito, non inventare dosaggi o indicazioni, dichiarare esplicitamente quando l'informazione non c'è, citare sempre documento + sezione + paragrafo + span, non dare consigli medici personalizzati.

La risposta del modello viene normalizzata: le fonti "precise" sono quelle del retrieval (hanno offset e testo esatto); se il retrieval non ne ha, si usano quelle generate dal modello.

### Memoria

`MemorySaver` usa `thread_id = sessione_id`. Il frontend mantiene lo `sessione_id` restituito dal backend e rimanda lo storico a ogni richiesta. Va notato che oggi il backend restituisce `"default"` quando il client non passa un id, quindi la memoria è **di fatto condivisa** tra sessioni; lo storico esplicito nel body è ciò che rende la conversazione coerente. È un punto da rifinire prima della demo (generare un UUID per sessione).

## 7. Frontend

Stack: **Next.js 16.4.5**, React 19.3.0, TypeScript, Tailwind CSS 3.4. Nessuna libreria UI esterna.

### Home (`src/app/page.tsx`)

- carica la lista farmaci dal backend;
- **ricerca live** con debounce di 150 ms (`SearchBar`);
- griglia di 5 schede cliccabili;
- piccolo blocco "Come funziona".

### Dettaglio (`src/app/farmaco/[id]/`)

Architettura a due file, necessaria per Next 16:

- `page.tsx` è un **Server Component** che `await params` (in Next 16 `params` è una Promise) e passa `farmacoId` come prop;
- `ClientPage.tsx` è il componente client con stato e interazioni.

All'apertura viene chiamato **solo** `/api/farmaco/{id}`: nessuna chiamata al modello. Il pannello sinistro mostra subito il foglio originale.

Azioni disponibili:

| Azione | Effetto |
|--------|---------|
| 💬 Chiedi al chatbot | apre il popup; la risposta cita le fonti e la prima viene evidenziata in giallo nell'originale |
| 🪄 Semplifica testo | chiama `/api/simplify`, mostra spinner, poi il pannello destro ETR |
| Ascolta versione facile | chiama `/api/tts`, riceve un WAV e lo riproduce con `HTMLAudioElement` |

### Componenti

| Componente | Ruolo |
|------------|-------|
| `SearchBar` | input con debounce, dropdown risultati, spinner |
| `OriginalDocument` | pannello originale a blocchi, con evidenziazione per `blocco_id` |
| `HighlightSpan` | trova la prima occorrenza case-insensitive dello span e la racchiude in `<mark>` |
| `EasyText` | una frase, elenco ETR, glossario, domande per il farmacista |
| `ChatButton` + `ChatPanel` | apertura pannello laterale, invio messaggi, storico, fonti |

### TTS

La sintesi vocale è **server-side** tramite OpenRouter TTS con il modello
`heygen/heygen-voice-1-turbo:free`. Il backend chiama
`POST /api/v1/audio/speech`, riceve PCM, lo converte in WAV a 16 kHz e lo
restituisce al browser, che lo riproduce con `HTMLAudioElement`.

Vantaggi: voce coerente su tutti i dispositivi, nessuna dipendenza dalle voci
installate nel sistema operativo, qualità controllabile. L'audio viene messo
in cache su disco per testo+voce+modello, quindi riascoltare la stessa
versione non richiama il provider. La voce è configurabile con `TTS_VOICE`.

Il testo della versione facile viene diviso in chunk di circa 600 caratteri:
il frontend li sintetizza e li riproduce in sequenza. In questo modo la prima
frase parte subito, ogni risposta resta piccola e non si creano WAV da decine
di MB. La route proxy Next inoltra l'audio in streaming, senza bufferizzarlo.

## 8. Configurazione LLM

Provider: **OpenRouter**, quindi il backend è **model-agnostic**: si cambia modello nel `.env` senza toccare il codice.

```env
OPENROUTER_API_KEY=...
CHAT_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
SIMPLIFY_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
```

La factory condivisa `backend/app/llm.py` centralizza la creazione del client:

- `reasoning: { "enabled": false }` — **necessario**: Nemotron è un modello *reasoning*, consumava i token nel "pensiero" e restituiva `content: null`;
- timeout ampio (90 s configurabile con `LLM_TIMEOUT`) — il free tier risponde in 10–30 s;
- `max_retries=0` — i retry automatici raddoppiavano la latenza percepita.

## 9. Difficoltà incontrate e soluzioni

| Problema | Causa | Soluzione |
|----------|-------|-----------|
| "Semplifica" non faceva nulla | 5 bug sovrapposti (import mancante, modello reasoning, timeout 10 s, `KeyError` nel prompt di rerank, rerank troppo severo) | import corretto, reasoning off, timeout 90 s, graffe escaping + parser JSON robusto, best-effort sul miglior candidato |
| Risposte del chatbot "informazione non trovata" | l'indice conteneva più formulazioni; il retrieval pescava l'endovenosa invece delle compresse | filtro sul primo foglio, BM25 con IDF, contesto su 3 blocchi |
| `content: null` dal modello | Nemotron spende i token nel reasoning | `reasoning.enabled = false` |
| CORS / DNS dal browser | chiamata diretta al backend | proxy same-origin nelle API route di Next |
| Tailwind non applicato | Tailwind v4 incompatibile con Turbopack/`magic-string` | downgrade a v3 + `postcss.config.js` + `tailwind.config.js` |
| `params` undefined nel dettaglio | Next 16: `params` è una Promise | `page.tsx` server component con `await params` e prop al client |
| Evidenziazione fonte non collegata | callback non passata da `ChatButton` | `onHighlightSource` propagata fino a `OriginalDocument` |

## 10. Stato attuale verificato

| Funzione | Esito | Tempo osservato |
|----------|-------|-----------------|
| Apertura dettaglio (solo JSON, nessun LLM) | ✅ | ~0,1 s |
| Semplificazione di una sezione | ✅ | ~10 s |
| Semplificazione di tutte le sezioni | ✅ 18 frasi + glossario + domande | ~27 s |
| Chatbot "Posso prenderlo se ho il mal di testa?" | ✅ risposta corretta con fonte citata | ~6–9 s |
| Evidenziazione della fonte nell'originale | ✅ | — |
| Ricerca live in home | ✅ keyword | immediata |
| TTS | ✅ HeyGen Voice Turbo via OpenRouter | ~1–2 s; cache su disco |
| Build TypeScript + `next build` | ✅ | — |

Server attivi in sviluppo: backend `:8000`, frontend `:3000`.

## 11. Limiti noti e prossimi passi

In ordine di priorità per la demo:

1. **Sessione chat**: generare un `sessione_id` univoco lato backend e non usare `"default"` per tutti.
2. **Fallback del chatbot non funzionante**: `carica_markdown` costruisce un nome file inesistente (`TACHIPIRINA_1000_FI.md`) e il match per sottostringa non trova `TACHIPIRINA_FI.md`. Il ramo di fallback restituisce quindi "non trovato" invece di leggere il markdown. Va corretto il mapping id → file.
3. **Ricerca semantica**: implementare davvero il fallback LLM di `/api/search` (o embeddings) per sinonimi e domande in linguaggio naturale.
4. **Qualità del retrieval**: il rerank usa un solo blocco come "principale"; valutare top-k con soglia di score e citazioni multiple.
5. **Latenza**: il free tier è lento. Le semplificazioni sono ora in cache persistente su disco; a regime servono streaming e cache condivisa.
6. **UX risultati di ricerca**: il dropdown mostra lo slug (`tachipirina_1000`) invece del nome leggibile.
7. **Semplificazione dell'originale**: il pannello sinistro unisce le 6 sezioni JSON; per un allineamento perfetto con le citazioni conviene renderizzare il markdown completo con la struttura delle sezioni.
8. **Accessibilità**: verificare contrasti, focus da tastiera, ARIA nel popup chat, dimensione del testo regolabile.
9. **Persistenza**: oggi `MemorySaver` è in RAM; per sessioni persistenti servirebbe un checkpointer su DB.
10. **Sicurezza**: la chiave OpenRouter sta nel `.env` del backend (mai nel frontend); prima di un deploy va gestita con un secret manager e va aggiunto rate limiting.

## 12. Come avviarlo

### Backend

```bash
cd farmaco-chiaro/backend
cp .env.example .env        # inserire OPENROUTER_API_KEY
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Indice (da rifare solo se cambiano i markdown):

```bash
uv run python index/build_index.py
```

### Frontend

```bash
cd farmaco-chiaro/frontend
npm install
npm run dev                 # sviluppo
# oppure
npm run build && npm start  # produzione, porta 3000
```

Aprire `http://localhost:3000`.

## 13. Mappa dei file principali

| File | Contenuto |
|------|-----------|
| `backend/app/main.py` | app FastAPI, CORS, mounting router |
| `backend/app/llm.py` | factory OpenRouter (reasoning off, timeout, no retry) |
| `backend/app/routes/farmaci.py` | lista e dettaglio dal catalogo JSON |
| `backend/app/routes/search.py` | ricerca keyword sui blocchi |
| `backend/app/routes/simplify.py` | prompt ETR, parsing JSON, fallback |
| `backend/app/routes/chat.py` | endpoint chat, guardia API key |
| `backend/graph/chat_graph.py` | grafo LangGraph, prompt, memoria, `run_chat` |
| `backend/tools/markdown_tool.py` | BM25, estrazione paragrafo, caricamento markdown |
| `backend/index/build_index.py` | indicizzazione markdown → `blocchi.json` |
| `backend/data/catalogo_farmaci.json` | preview dei 5 farmaci (6 sezioni) |
| `backend/data/markdown/FI/*.md` | fonte di conoscenza del chatbot |
| `frontend/src/app/page.tsx` | home con ricerca live |
| `frontend/src/app/farmaco/[id]/page.tsx` | server component, `await params` |
| `frontend/src/app/farmaco/[id]/ClientPage.tsx` | split-screen, semplifica, TTS |
| `frontend/src/components/ChatPanel.tsx` | pannello chat laterale, storico, fonti |
| `frontend/src/components/HighlightSpan.tsx` | evidenziazione dello span citato |
| `frontend/src/app/api/**/route.ts` | proxy verso FastAPI |

---

## 14. Aggiornamento post-refactoring (7 novembre 2026)

Questa sezione descrive lo stato dopo il refactoring "demo robusta,
production-shaped". Le sezioni precedenti restano la descrizione dell'idea e
della demo originale; dove c'è divergenza, vale questa sezione.

### Correzioni P0

- Il file `TACHIPRINA_FI.md` (nome errato) è stato rinominato in
  `TACHIPIRINA_FI.md`. Anche la RCP è stata allineata.
- Introdotto `backend/data/farmaci.json` come **registro unico**
  `id -> file FI/RCP + titolo documento`. `build_index.py`,
  `markdown_tool.py` e la ricerca non hanno più mappe duplicate.
- `build_index.py` ora valida i file, fallisce se un farmaco non produce
  blocchi, produce `index_meta.json` e supporta `--check` per la CI.
- Corretto il fallback del chatbot: `carica_markdown()` usa il registro e
  funziona per tutti e 5 i farmaci. Il fallback recupera i chunk pertinenti
  del markdown completo, non i primi 3.000 caratteri.
- Corretta la macchina a stati del dettaglio: lo stato di errore non è più
  irraggiungibile e non c'è più lo spinner infinito.
- `sessione_id` è un UUID generato dal backend se assente; `"default"` è
  stato eliminato. `MemorySaver` è stato rimosso: la chat è stateless e la
  history viaggia nel body ed è usata nel prompt.
- `.env` è ignorato da Git; CORS è ristretto alle origini configurate; gli
  errori interni non vengono più restituiti al client.

### Architettura

- Nuovi moduli: `app/config.py`, `app/farmaci.py`, `app/schemas.py`,
  `app/json_utils.py`, `services/retrieval.py`, `services/documento.py`,
  `services/citazioni.py`, `services/simplify.py`, `services/cache.py`,
  `services/tts.py`.
- Nuovo endpoint `GET /api/farmaci/{id}/documento`: restituisce il foglio
  sezionato in blocchi citabili (`blocco_id`, paragrafo, testo).
- Il pannello sinistro del frontend non usa più `Object.values(sezioni)`:
  renderizza il documento a blocchi, con titoli, e la fonte citata viene
  evidenziata per `blocco_id` con scroll automatico.
- Tutte le chiamate del browser passano dalle route proxy same-origin di
  Next (`/api/farmaci`, `/api/search`, `/api/chat`, `/api/simplify`,
  `/api/tts`, `/api/farmaco/[id]/documento`). `BACKEND_URL` è server-side.
- Graph semplificato: `recupera -> genera | espandi -> recupera -> genera |
  fallback`. L'espansione LLM avviene solo se la query originale non trova
  blocchi. Il rerank LLM separato è stato rimosso; si generano al massimo 3
  blocchi di contesto.
- Le fonti prodotte dal modello vengono validate contro i blocchi: se lo
  span citato non è contenuto nel blocco, la fonte viene scartata e si usa
  quella del retrieval.
- Il retrieval applica un boost per intento (gravidanza, allattamento,
  bambini, dosaggio, effetti indesiderati, alcol): per "sono incinta"
  privilegia i blocchi "Gravidanza"/"trimestre" anche quando la domanda non
  contiene la parola "gravidanza".
- Esiste anche un intento di **condivisione** ("posso darlo a un parente?"):
  riconosce frasi come "Non lo dia ad altre persone" e "prescritto soltanto
  per lei" nel corpo del blocco, non solo nel titolo.
- Le citazioni vengono **affinate**: se il modello restituisce l'intero
  blocco, viene scelta la frase più pertinente (con la frase adiacente solo
  se condivide parole con domanda/risposta). Le fonti poco pertinenti
  rispetto alla risposta vengono scartate.
- I blocchi dell'indice vengono ripuliti dal footer legale AIFA, che non può
  quindi diventare una fonte citata.
- Il contesto passa al modello anche il `blocco_id`. La chat mostra tutte le
  fonti con un pulsante "Vai alla fonte"; il click forza lo scroll e
  l'evidenziazione anche se quella fonte è già attiva.
- La semplificazione non tronca più silenziosamente a 6.000 caratteri:
  chunking con merge e pulizia degli artefatti OCR. Il risultato viene salvato
  in una **cache persistente su disco** in `backend/data/cache/simplify/`,
  con chiave `prompt_version + modello + hash(testo)`. Il parametro
  `forza: true` rigenera ignorando la cache.
- La versione facile è volutamente **sintetica**: massimo 7 frasi, 3 voci di
  glossario e 3 domande. Il prompt chiede solo l'essenziale (a cosa serve, come
  si prende, principali avvertenze); i dettagli restano nel foglio originale e
  nella chat. L'input viene preso dai blocchi del documento, così non si
  mescolano formulazioni diverse.
- Nuovo endpoint `POST /api/tts`: usa OpenRouter TTS
  (`heygen/heygen-voice-1-turbo:free`), converte PCM→WAV a 16 kHz e mette
  l'audio in cache in `backend/data/cache/tts/`. Il frontend riproduce il WAV
  con `HTMLAudioElement`, senza dipendere dalle voci del browser.

### Qualità e operatività

- Test backend con pytest (registro, retrieval, documento, citazioni, API,
  chunking, cache, conversione audio). 24 test verdi.
- `ruff` per il backend; ESLint pulito per il frontend; `next build` verde.
- `docker-compose.yml` + Dockerfile per backend e frontend.
- CI GitHub Actions: pytest, `build_index.py --check`, ESLint, `next build`.
- `Makefile` con `make dev`, `make index`, `make test`, `make build`,
  `make up`.

### Limiti ancora aperti

- La semplificazione usa ancora il catalogo preview come input, non i blocchi
  del documento: è il prossimo passo per allineare completamente input e
  citazioni.
- La ricerca è ancora lessicale (BM25). L'interfaccia `services/retrieval.py`
  è pronta per un adapter embeddings.
- Le sessioni sono stateless: per la produzione serve un `SessionStore`
  (Redis/DB) con TTL.
- Il rate limiting e l'osservabilità strutturata sono predisposti a livello
  architetturale ma non ancora implementati.

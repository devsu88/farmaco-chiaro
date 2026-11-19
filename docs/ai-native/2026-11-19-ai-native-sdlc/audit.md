# Audit AI-native SDLC — 2026-11-19

Stato del repository rispetto ai sei stadi del playbook. È la fotografia
prima dell'intervento; le azioni della colonna destra sono quelle incluse in
questa iniziativa. Ciò che resta fuori è elencato in fondo.

## Quadro per stadio

| Stadio | Stato attuale | Gap | Azione in questa iniziativa |
|---|---|---|---|
| **Plan** | Nessun artefatto di intent; le decisioni vivono in `REPORT.md` (ignorato) e nella history Git | L'idea non ha una casa versionata; un agente non sa perché una scelta è stata presa | `docs/ai-native/` con convenzione e `intent.md` di questo intervento |
| **Design** | Il design è nel `README.md` e nei commenti; nessuna spec con requisiti verificabili | Le policy (medica, sicurezza, UX) non sono applicate mentre si scrive la spec | `spec.md` con requisiti, rischi, criteri di accettazione |
| **Build** | Nessun `AGENTS.md`; `.opencode/agents/` esiste ma è ignorato; nessuna skill | La conoscenza istituzionale non è condivisa né auditabile | `AGENTS.md`, `.opencode/skills/`, `opencode.jsonc`, agenti tracciati |
| **Test** | 169 test, golden set, eval densa, fallback deterministico | La configurazione dell'agente (prompt, skill, scenari) non è regression-tested | `test_safety_contract.py`, checker di processo, workflow dedicato |
| **Deploy** | Vercel Services, cron keepalive, CI test/lint/build | Nessuna policy di review, nessun template, nessun runbook di rollback esplicito | `REVIEW.md`, template PR, deploy/rollback in `AGENTS.md` |
| **Maintain** | Keepalive Qdrant giornaliero; nessun loop incidente → intent | Gli incidenti non rientrano nel processo | Loop documentato in `docs/ai-native/README.md` |

## Cosa funziona già

- **Grounding reale, non dichiarato.** Le risposte della chat sono costruite
  sui blocchi recuperati; `services/citazioni.py` valida, affina e filtra le
  fonti. La UI evidenzia il blocco citato.
- **Fallback onesto.** Se Qdrant o gli embedding non rispondono, il retrieval
  usa BM25. La guida è deterministica e non chiama il modello.
- **Test deterministici.** `conftest.py` forza `RETRIEVAL_MODE=bm25`; i test
  non dipendono da provider esterni. 169 test, non 106 come dice `REPORT.md`.
- **Golden set e eval.** 15 domande con blocchi attesi in
  `backend/tests/data/golden_set.json`; 30 domande di retrieval in
  `backend/eval/qa.jsonl` con recall@5 e MRR.
- **Dati runtime committati.** `backend/data/rag/` contiene 621 farmaci,
  12.947 chunk, 3.624 sezioni e 11.199 blocchi: il container parte senza
  ingestion.
- **Sicurezza medica già scritta.** L'agente `medical-content-guardian`
  contiene le regole giuste; il problema è che non era versionato.

## Gap che questa iniziativa chiude

1. Assenza di `AGENTS.md`/`REVIEW.md` e di artefatti `intent/spec/plan`.
2. `.opencode/` ignorato: agenti e conoscenza non condivisi.
3. Nessuna eval sulla configurazione dell'agente.
4. Nessun template di PR con prove, rischio e rollback.
5. Drift tra `REPORT.md` e il codice attuale.

## Gap che restano (opzione C)

Questi non sono cosmetici; sono i rischi di produzione più concreti.

| Priorità | Gap | Perché conta |
|---|---|---|
| P1 | `/api/simplify` accetta `testo` arbitrario; `/api/chat` accetta storico illimitato | Costo e abuso del provider; prompt injection sul testo libero |
| P1 | Nessun rate limit o quota per IP/sessione sugli endpoint LLM | Una demo pubblica può essere consumata da un singolo client |
| P1 | Il proxy Next non impone un timeout alle chiamate al backend | Una richiesta lenta tiene occupata una funzione |
| P2 | Nessun log strutturato, metrica o trace (OTel) | Non si può chiudere il loop di manutenzione senza metriche |
| P2 | Cache su disco locale nel container | Su Vercel non è condivisa né persistente; il colpo di cache è per istanza |
| P2 | Sessione chat stateless | Follow-up e costi dipendono dal client |
| P3 | `make eval` non gira in CI | La qualità densa non ha una regressione automatica |
| P3 | Nessuna revisione medica indipendente | È un rischio di prodotto, non di codice |

## Giudizio

La base è sopra la media per un progetto di questa dimensione: il prodotto è
grounded, i test sono reali e il fallback è progettato. Il divario rispetto al
playbook non è nella qualità del codice, è nel fatto che il processo non è un
artefatto. Questa iniziativa chiude quel divario per Plan, Design, Build, Test
e Deploy; Maintain resta documentato e l'hardening resta il prossimo lavoro.

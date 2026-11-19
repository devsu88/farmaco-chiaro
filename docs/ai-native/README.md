# AI-native SDLC — casa degli artefatti

Questa cartella è la fonte di verità del processo di cambiamento. Ogni
iniziativa non banale lascia qui la catena `intent → spec → plan` e, quando
serve, un audit o un record di incidente. Gli agenti e le persone leggono gli
stessi file.

Il modello è quello del playbook *The AI-native SDLC*: ogni stadio produce un
artefatto versionato che lo stadio successivo può leggere. Il commit è la
traccia di audit.

## Struttura

```text
docs/ai-native/
├── README.md                       # questo file: convenzioni e ciclo
└── YYYY-MM-DD-<slug>/
    ├── intent.md                   # problema, esito, vincoli, domande aperte
    ├── spec.md                     # requisiti + design, con i rischi
    ├── plan.md                     # file, ordine, test, prove
    └── audit.md                    # facoltativo: stato e gap
```

`<slug>` è kebab-case e descrive il cambiamento, non il ticket. Per un
intervento piccolo la `spec` può stare in poche righe, ma non si salta.

## Il ciclo

| Stadio | Artefatto | Chi approva | Cosa fa partire lo stadio successivo |
|---|---|---|---|
| Plan | `intent.md` | product owner | intent accettato |
| Design | `spec.md` | product owner + technical lead per i rischi alti | spec accettata |
| Build | `plan.md` + diff + test | engineer | piano accettato |
| Test | output di `make test` / `make check` + verifica browser | engineer | prove allegate alla PR |
| Deploy | PR + `REVIEW.md` + autorizzazione al rilascio | code owner + release manager | merge e deploy |
| Maintain | nuovo `intent.md` da incidente o metrica fuori banda | on-call / service owner | triage |

Il loop si chiude quando un incidente, un errore ricorrente o una metrica fuori
banda diventano un `intent.md`, non un ticket nel backlog.

## Cosa scrivere in ogni artefatto

### intent.md

- Autore e data.
- Problema, in parole di chi lo ha visto.
- Esito proposto e come si riconosce che è raggiunto.
- Utenti e sistemi toccati.
- Vincoli (sicurezza, dati, costi, tempi).
- Non-obiettivi espliciti.
- Domande aperte, con chi le risolve.

### spec.md

- Requisiti numerati e verificabili.
- Design: dove vive il codice, quali interfacce cambiano.
- Rischi e mitigazioni.
- Criteri di accettazione: comandi e output attesi.
- Aree di preoccupazione: policy contraddittorie, debito noto, cose che non
  si possono soddisfare.

### plan.md

- File creati e modificati, con i test.
- Ordine dei task, ognuno con il proprio ciclo di verifica.
- Rischi del cambiamento e blast radius.
- Prove: comandi esatti e risultato atteso.
- Aggiornare il piano nello stesso commit quando l'implementazione se ne
  discosta.

## Regole

- Un solo sistema è fonte di verità per artefatto: qui il repository.
- `AGENTS.md` è la guida operativa degli agenti; `REVIEW.md` è la policy di
  review. Non duplicare il contenuto: linkare.
- I test del contratto di sicurezza (`backend/tests/test_safety_contract.py`)
  e il controllo degli artefatti (`scripts/check_ai_native.py`) girano in CI
  quando cambiano prompt, skill, hook o configurazione dell'agente.
- Niente segreti negli artefatti. Le variabili d'ambiente si descrivono, non si
  copiano.

## Metriche da guardare

Il playbook propone indicatori leading e lagging. Per questo repository:

| Indicatore | Dove si legge |
|---|---|
| Tempo da prima conversazione a `intent.md` committato | git log della cartella |
| Rework della spec dopo l'inizio del build | commit su `spec.md` dopo il primo `plan.md` |
| Successo CI al primo passaggio | GitHub Actions |
| Tasso di superamento delle eval di configurazione | job `AI-native evals` |
| Finding di review per PR, e quanti sono Important | PR history |
| Tempo da incidente a `intent.md` | issue/incident tracker + git |

## Manutenzione

- Un incidente di produzione produce un `intent.md` nella forma qui sopra.
- Un errore che si ripete due volte produce una regola in `AGENTS.md` o in una
  skill, non solo una correzione puntuale.
- Una scansione periodica dei repository produce fix piccoli come PR e, se il
  fix è più grande di una PR, un `intent.md`.
- La revisione umana resta il gate: nessun agente approva il proprio lavoro.

# Spec: SDLC AI-native per Farmaco Chiaro

Data: 2026-11-19. Deriva da `intent.md` nella stessa cartella.

## Obiettivo

Rendere il processo di cambiamento un artefatto del repository, senza toccare
il comportamento del prodotto. La base tecnica esistente (169 test, golden set,
citazioni ancorate, fallback BM25) resta com'è; si aggiunge il livello che il
playbook chiama *governance e continuità*.

## Requisiti

### R1 — Guida operativa degli agenti

`AGENTS.md` alla root contiene comandi, architettura, fonte di verità,
invarianti medici, gotcha, deploy e rollback. `CLAUDE.md` è un puntatore a
`AGENTS.md` per Claude Code; OpenCode legge `AGENTS.md` nativamente.

**Verifica:** `AGENTS.md` esiste e contiene `make test`, `make lint`,
`make build`, `make check`, `REVIEW.md`, `docs/ai-native`.

### R2 — Policy di review

`REVIEW.md` definisce i passaggi (bug, sicurezza, sicurezza medica,
conformità a spec/piano, prove), cosa significa *Important*, il limite ai nit
e cosa non riportare. La review umana resta il gate.

**Verifica:** il file contiene le sezioni `Passes`, `Important`, `Nit`.

### R3 — Catena di artefatti

`docs/ai-native/README.md` spiega convenzioni e ciclo. Ogni iniziativa vive in
`docs/ai-native/<YYYY-MM-DD>-<slug>/` con `intent.md`, `spec.md`, `plan.md`.
Questa iniziativa è il primo esempio.

**Verifica:** il checker trova almeno una cartella con i tre file non vuoti.

### R4 — Skill di progetto

Due skill in `.opencode/skills/`:

- `medical-content-safety`: regole bloccanti per prompt, semplificazione,
  scenari, guida, scheda e copy UI.
- `ai-native-change`: il workflow intent → spec → plan → build → test →
  review → deploy → maintain, con i comandi di verifica.

**Verifica:** ogni `SKILL.md` ha frontmatter con `name` e `description`; l'ID
è kebab-case e coincide con la cartella.

### R5 — Guardrail deterministici

`opencode.jsonc` impedisce la lettura e la modifica dei file `.env*` (tranne
`.env.example`), la modifica a mano degli artefatti generati e i comandi
distruttivi; chiede conferma per push, deploy di produzione, rollback e
reindicizzazione.

**Verifica:** il file è JSONC valido e contiene le regole per `.env`,
`backend/data/rag/*.jsonl`, `git push --force*`, `vercel --prod*`.

### R6 — Conoscenza condivisa

`.opencode/agents/` e `.opencode/skills/` sono tracciati da git. Restano
ignorati solo stato locale e artefatti di tooling (`.superpowers/`,
`.playwright-mcp/`, cache, build).

**Verifica:** `git ls-files` include gli agenti; il checker rifiuta file
tracciati vietati.

### R7 — Eval di configurazione in CI

`scripts/check_ai_native.py` verifica artefatti, frontmatter, segreti
tracciati e presenza dei dati runtime. `backend/tests/test_safety_contract.py`
blocca la deriva dei prompt e del contratto degli scenari. Un workflow
dedicato li esegue quando cambiano prompt, skill, agenti o artefatti, più una
volta a settimana.

**Verifica:** `python3 scripts/check_ai_native.py` esce 0; i test di sicurezza
passano; il workflow è valido.

### R8 — Template di PR

`.github/pull_request_template.md` chiede artefatti collegati, prove eseguite,
blast radius, checklist medica e rollback.

**Verifica:** il file esiste e contiene le sezioni.

### R9 — Allineamento documentale

`README.md` cita il nuovo comando `make check` e la sezione per chi lavora con
gli agenti. `REPORT.md`, che è storico e ignorato da git, riceve un banner che
lo dichiara superato.

**Verifica:** `README.md` contiene `make check`; `REPORT.md` inizia con il
banner.

## Design

### Perché OpenCode-native e non una copia di Claude Code

Il repository usa OpenCode. I concetti del playbook hanno equivalenti nativi:

| Playbook | Qui |
|---|---|
| `CLAUDE.md` | `AGENTS.md` (+ `CLAUDE.md` puntatore) |
| `.claude/skills/` | `.opencode/skills/` |
| hook di build | `opencode.jsonc` → `permissions` |
| subagenti | `.opencode/agents/` |
| eval di configurazione | `scripts/check_ai_native.py` + test di contratto |
| review policy | `REVIEW.md` + template PR |

Non si aggiungono file `.claude/` paralleli: sarebbero una seconda fonte di
verità. `CLAUDE.md` resta un import di una riga.

### Perché i guardrail sono permessi e non un plugin

Un plugin che ispeziona comandi shell è più potente ma fragile: il parsing dei
comandi composti è best effort. I permessi sono deterministici per le azioni
che coprono (read/edit/shell) e non introducono codice da mantenere. Le regole
che richiedono giudizio (non indebolire i test, non separare un avvertimento
dal suo contesto) restano nelle skill e nella review, dove servono.

### Perché la eval di configurazione è stdlib-only

La CI non deve avere credenziali per girare. Il checker usa solo la standard
library e `git ls-files`; i test di sicurezza importano i prompt e i dati già
presenti. La eval densa (`make eval`) resta un comando manuale perché richiede
Qdrant e il provider di embedding.

### Cosa non si tocca

Nessuna route, nessun prompt, nessun dato. Le uniche modifiche a file esistenti
sono: `.gitignore` (toglie `.opencode/`), `Makefile` (aggiunge `check`),
`ci.yml` (aggiunge il job di processo), `README.md` (documentazione),
`REPORT.md` (banner).

## Criteri di accettazione

1. `python3 scripts/check_ai_native.py` esce 0.
2. `cd backend && uv run pytest -q tests/test_safety_contract.py` passa.
3. `make test` resta verde.
4. `git ls-files` non contiene `.env` né artefatti di build/cache.
5. `.opencode/agents/` e `.opencode/skills/` sono tracciati.
6. Il workflow `AI-native evals` è presente e valido.
7. Nessuna modifica a `backend/app/`, `backend/services/`, `backend/graph/` o
   `frontend/src/`.

## Rischi e mitigazioni

| Rischio | Mitigazione |
|---|---|
| I test di contratto sono fragili se i prompt cambiano per una ragione legittima | I test verificano clausole di sicurezza, non il testo completo; si aggiornano insieme alla spec |
| I permessi bloccano un'operazione legittima | Le regole `deny` coprono solo segreti, generati e force-push; il resto è `ask` |
| Il checker duplica ciò che fa già la CI | Il checker copre il processo, non il prodotto; il job è veloce e separato |
| Il team usa Claude Code e non OpenCode | `CLAUDE.md` importa `AGENTS.md`; skill e agenti restano in `.opencode/` e sono leggibili come markdown |

## Aree di preoccupazione

- La revisione medica indipendente non è risolta da questo intervento: è una
  domanda aperta nell'`intent`.
- Il loop di manutenzione è documentato, non automatizzato. Automatizzarlo
  richiede metriche e un ambiente con credenziali, fuori dall'opzione B.
- `make eval` non gira in CI: la qualità densa resta verificata a mano. È
  accettato per ora, ma va rivalutato quando il golden set cresce.

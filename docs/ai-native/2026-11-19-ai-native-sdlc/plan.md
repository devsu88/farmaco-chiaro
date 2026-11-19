# Plan: SDLC AI-native per Farmaco Chiaro

Deriva da `spec.md` nella stessa cartella. Esecuzione nativa in questa
sessione, un task per volta.

**Goal:** aggiungere al repository gli artefatti e i guardrail del ciclo
AI-native, senza cambiare il comportamento del prodotto.

**Architecture:** OpenCode-native (AGENTS.md, `.opencode/skills`, permissions)
con `CLAUDE.md` come puntatore. La catena intent/spec/plan vive in
`docs/ai-native/`. La CI verifica artefatti e deriva dei prompt con uno script
stdlib-only e test di contratto.

**Tech stack:** Python 3.13, pytest, FastAPI, Next.js 16, GitHub Actions,
OpenCode V2.

## Task

### Task 1 — Contratti alla root

**File:** `AGENTS.md` (nuovo), `CLAUDE.md` (nuovo), `REVIEW.md` (nuovo),
`opencode.jsonc` (nuovo).

- [x] Scrivere `AGENTS.md` con comandi, architettura, fonte di verità,
  invarianti medici, gotcha, deploy/rollback.
- [x] Scrivere `CLAUDE.md` come import di una riga (`@AGENTS.md`).
- [x] Scrivere `REVIEW.md` con i cinque passaggi e la definizione di
  *Important*.
- [x] Scrivere `opencode.jsonc` con i permessi su segreti, generati, push,
  deploy e reindicizzazione.

**Verifica:** i quattro file esistono e il checker li accetta.

### Task 2 — Casa degli artefatti

**File:** `docs/ai-native/README.md`, `docs/ai-native/2026-11-19-ai-native-sdlc/{intent,spec,plan,audit}.md`.

- [x] Scrivere la convenzione e il ciclo in `README.md`.
- [x] Scrivere `intent.md` (problema, esito, vincoli, non-obiettivi, domande).
- [x] Scrivere `spec.md` (requisiti, design, criteri, rischi).
- [x] Scrivere `audit.md` (sei stadi, gap chiusi, gap residui).
- [x] Scrivere questo `plan.md`.

**Verifica:** il checker trova la cartella con i tre file obbligatori.

### Task 3 — Skill di progetto

**File:** `.opencode/skills/medical-content-safety/SKILL.md`,
`.opencode/skills/ai-native-change/SKILL.md`.

- [x] `medical-content-safety`: regole bloccanti, checklist, comandi di
  verifica, formato dei finding.
- [x] `ai-native-change`: quando si applica, catena degli artefatti, TDD,
  comandi, definition of done.

**Verifica:** frontmatter con `name` e `description`; ID kebab-case.

### Task 4 — Guardrail e conoscenza condivisa

**File:** `.gitignore` (modifica), `.opencode/agents/**` (tracciare).

- [x] Togliere `.opencode/` da `.gitignore`; lasciare ignorati
  `.superpowers/`, `.playwright-mcp/`, cache e build.
- [x] Verificare che i 12 agenti e il README siano tracciabili.

**Verifica:** `git ls-files` include `.opencode/agents/*.md`; il checker non
trova file vietati.

### Task 5 — Eval di configurazione e CI

**File:** `scripts/check_ai_native.py` (nuovo),
`backend/tests/test_safety_contract.py` (nuovo),
`.github/workflows/ai-native.yml` (nuovo), `.github/workflows/ci.yml`
(modifica), `.github/pull_request_template.md` (nuovo), `Makefile` (modifica).

- [x] Scrivere il checker: file obbligatori, frontmatter di skill e agenti,
  segreti tracciati, artefatti runtime, JSONC valido.
- [x] Scrivere i test di contratto: clausole di grounding nella chat, limiti e
  dosaggi nella semplificazione, contratto degli scenari, escalation 112.
- [x] Aggiungere il workflow path-filtered + settimanale che esegue checker e
  test di sicurezza/golden set.
- [x] Aggiungere il job `process` a `ci.yml`.
- [x] Aggiungere il template di PR (artefatti, prove, rischio, checklist
  medica, rollback).
- [x] Aggiungere `make check` = `test` + build + checker.

**Verifica:** `python3 scripts/check_ai_native.py` esce 0; i test nuovi
passano; `make test` resta verde.

### Task 6 — Allineamento documentale

**File:** `README.md` (modifica), `REPORT.md` (banner, file ignorato).

- [x] Aggiungere `make check` alla tabella comandi.
- [x] Aggiungere una sezione "Working with agents" con i link.
- [x] Mettere un banner di storico in cima a `REPORT.md`.

**Verifica:** `README.md` contiene `make check`; `REPORT.md` inizia con il
banner.

### Task 7 — Verifica finale

- [x] `python3 scripts/check_ai_native.py`
- [x] `cd backend && uv run pytest -q tests/test_safety_contract.py`
- [x] `make test`
- [x] `make build` (solo se il tempo lo consente; nessuna modifica frontend)
- [x] `git diff --stat` e controllo che `backend/app`, `backend/services`,
  `backend/graph`, `frontend/src` siano intatti.

## Rischi

| Rischio | Mitigazione |
|---|---|
| Permessi troppo stretti bloccano il lavoro | Solo `deny` su segreti/generati/force-push; il resto `ask` |
| Test di contratto fragili | Verificano clausole, non il testo intero |
| La CI fallisce per path sbagliati | Il workflow include i percorsi caldi e ha `workflow_dispatch` |
| Duplicazione tra README e AGENTS | README resta descrittivo; AGENTS è operativo; i link evitano copie |

## Prove

| Comando | Atteso |
|---|---|
| `python3 scripts/check_ai_native.py` | `OK` con il conteggio di skill/agenti |
| `uv run pytest -q tests/test_safety_contract.py` | tutti verdi |
| `uv run pytest -q tests/test_golden_set.py` | recall/MRR sopra soglia |
| `make test` | pytest + ESLint verdi |
| `git ls-files \| grep -E '(^\|/)\.env$'` | nessun risultato |

## Risultato dell'esecuzione (2026-11-19)

- `make test`: **174 passed** (169 esistenti + 5 di contratto), ESLint pulito.
- `make build`: build di produzione Next.js completata, 17 route.
- `python3 scripts/check_ai_native.py`: `OK` — 14 artefatti obbligatori,
  2 skill, 12 agenti, 1 iniziativa, 148 file tracciati puliti, 621 farmaci.
- `git diff --name-only`: solo `.github/workflows/ci.yml`, `.gitignore`,
  `Makefile`, `README.md`; nessuna modifica a `backend/app`,
  `backend/services`, `backend/graph`, `frontend/src`.
- I file nuovi sono non tracciati: vanno aggiunti con
  `git add AGENTS.md CLAUDE.md REVIEW.md opencode.jsonc .opencode docs scripts
  .github backend/tests/test_safety_contract.py`.

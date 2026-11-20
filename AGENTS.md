# Farmaco Chiaro — agent guide

Read this before changing the repository. It carries the context a new
maintainer needs; `docs/ai-native/README.md` carries the change process.

## What this is

An Italian consumer-health app that makes AIFA medicine leaflets readable.
The original leaflet stays visible; a plain-language version and a cited chat
sit next to it. The app does not diagnose and does not replace a doctor or
pharmacist.

Users are often older adults, caregivers, and people with low health or
digital literacy. A wrong dose or a missing warning is a product failure, not
a cosmetic bug.

## Commands

| Command | Result |
|---|---|
| `make dev` | Backend on `:8000` and frontend on `:3000` |
| `make test` | Backend pytest + frontend ESLint |
| `make lint` | Ruff + ESLint |
| `make build` | Next.js production build |
| `make check` | `make test` + production build + process/artifact checks |
| `make dataset` | Regenerate `backend/data/rag/` from Markdown |
| `make index` | Embed chunks and load them into Qdrant (needs credentials) |
| `make eval` | Dense retrieval evaluation on `backend/eval/qa.jsonl` (needs Qdrant) |
| `make up` / `make down` | Docker Compose with local Qdrant |

Backend alone: `cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`.
Frontend alone: `cd frontend && npm run dev`.

## Architecture

- `frontend/` — Next.js 16 App Router. It owns the UI and the same-origin
  `/api/*` proxy to the backend. The browser never calls FastAPI directly.
- `backend/app/` — FastAPI app, config, Pydantic schemas, thin routes.
- `backend/services/` — retrieval, citations, simplification, caching, TTS,
  guided mode, scenarios, share card.
- `backend/graph/chat_graph.py` — LangGraph chat graph. Stateless: history
  arrives from the client.
- `backend/aifa_rag/` — AIFA pipeline: manifest → PDF text → Markdown →
  chunks/sections/document blocks → Qdrant.
- `backend/data/rag/` — committed runtime snapshot used by the container.
  Source Markdown, embeddings, PDFs and cache stay out of git.

## Source of truth

1. `backend/data/rag/markdown/` is the leaflet source used to build the index.
2. `backend/data/rag/*.jsonl` and `farmaci.json` are **generated** artifacts.
   Never hand-edit them: run `make dataset` and commit the regenerated files.
3. `backend/data/scenari.json` is curated safety copy, not generated.
4. `README.md` and this file describe the current system. `REPORT.md` is a
   historical, git-ignored working note; do not treat it as current.

## Non-negotiables

### Medical safety

- Never diagnose, name a likely condition, or suggest starting, stopping or
  changing a medicine.
- Never state a dose, frequency or duration that is not literally in the
  source leaflet. Keep numbers and units exact.
- Every factual health claim must map to a block ID or a named leaflet
  section. If the source does not cover it, say so and redirect to a doctor
  or pharmacist.
- Red flags (difficulty breathing, face/throat swelling, chest pain, loss of
  consciousness, severe bleeding, suicidal thoughts) escalate immediately to
  112/118 or the emergency department. Do not triage.
- Keep warnings next to the condition they apply to. Chunking must not split
  a warning from its context.
- Never call a medicine "safe", "harmless" or "without effects".
- The disclaimer must remain visible on every surface: chat, guided mode,
  scenarios, share card.

Use `.opencode/skills/medical-content-safety/SKILL.md` for the full checklist
and `.opencode/agents/medical-content-guardian.md` for a deep content review.

### Data and generated artifacts

- Do not edit `backend/data/rag/chunks.jsonl`, `sections.jsonl`,
  `documento.jsonl`, `farmaci.json` or `index_meta.json` by hand.
- Do not commit `.env*` files, API keys, cache, embeddings, PDFs or generated
  Markdown. `backend/.env.example` is the only env file in git.
- Never weaken or delete a failing test to make a change pass. For a bug fix,
  write the failing test first. Editing a test, the eval set
  (`backend/eval/`) or `backend/data/scenari.json` asks for approval on
  purpose: explain in the PR why the contract must change.

### Verification

- Tests run deterministically with `RETRIEVAL_MODE=bm25` (see
  `backend/tests/conftest.py`). Do not make tests depend on Qdrant or
  OpenRouter.
- Before reporting work complete, run `make test` and paste the result.
  Before a production change, also run `make build` and
  `python3 scripts/check_ai_native.py` (or `make check`).
- UI changes need a browser check of the touched flow, not only a build.

## Change workflow

Non-trivial work follows `docs/ai-native/README.md`:

`intent.md` → `spec.md` → `plan.md` → code + tests → review (`REVIEW.md`) →
deploy → maintain.

The artifacts live in `docs/ai-native/<YYYY-MM-DD>-<slug>/`. Keep `plan.md`
in sync with the diff when the implementation departs from the plan. Open the
PR with the artifact links and the verification output.

## Gotchas

- Next.js 16: `params` is a Promise in server components; `frontend/AGENTS.md`
  points at the versioned docs under `node_modules/next/dist/docs/`. Read them
  before writing frontend code.
- Tailwind is v3 on purpose. v4 is incompatible with the current Turbopack
  setup.
- Nemotron is a reasoning model: the shared client disables reasoning,
  otherwise `content` comes back `null`. `max_retries=0` is intentional.
- Retrieval is hybrid BM25 + Qdrant/RRF but must degrade to BM25 when Qdrant
  or embeddings are unavailable. Keep that fallback.
- The chat graph is stateless. A persistent session store is not implemented.
- Home search is lexical on purpose: it must answer on every keystroke without
  calling the embedding provider.
- Vercel containers have no persistent disk. Cache goes to `CACHE_DIR`; the
  Qdrant index is external.
- Rate limiting is in memory per instance (`backend/app/rate_limit.py`):
  20/min chat and simplify, 10/min TTS, 60 s window, per client IP. Input
  limits live in `backend/app/config.py` and `backend/app/schemas.py`. The
  Next proxy forwards `x-forwarded-for` and times out at `PROXY_TIMEOUT_MS`
  (default 100 s).

## Deploy and rollback

Production is Vercel Services (`vercel.json`): `frontend` + `backend`
container. A human must authorize production deploys. Preview deploys are
safe. Rollback means promoting the previous healthy deployment
(`vercel rollback` or the Vercel dashboard) and verifying `/api/rag/status`
and a drug page. Do not change production data or indexes without a rollback
plan.

## Where knowledge lives

- `REVIEW.md` — review passes and severity definitions.
- `docs/ai-native/` — intent, spec, plan and audit artifacts.
- `.opencode/skills/` — repeatable policies (medical safety, change workflow).
- `.opencode/agents/` — project-scoped specialist subagents.
- `opencode.jsonc` — deterministic permission guardrails.

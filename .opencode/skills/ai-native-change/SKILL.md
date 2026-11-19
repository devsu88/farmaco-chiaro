---
name: AI-native change workflow
description: Run a repository change through the AI-native SDLC. Use for any non-trivial feature, bugfix, refactor, prompt change, data regeneration, or deploy.
---

# AI-native change workflow

Use this for every change that is not a typo, a formatting fix, or a dependency
bump with a green CI. The artifact chain is the audit trail; the commit is the
record.

## 1. Intent

Create or update `docs/ai-native/<YYYY-MM-DD>-<slug>/intent.md`:

- author and date;
- the problem in the words of the person who saw it;
- the proposed outcome and how you know it is reached;
- affected users and systems;
- constraints, non-goals, open questions.

Do not copy a ticket. Write what is wanted and why.

## 2. Spec

Write `spec.md` from the intent:

- numbered, verifiable requirements;
- design: files, interfaces, data flow;
- risks and mitigations;
- acceptance criteria with exact commands and expected output;
- areas of concern, including policy contradictions you cannot satisfy.

If the spec and the intent disagree, fix the intent or the spec before code.

## 3. Plan

Write `plan.md`:

- files created and modified, with tests;
- order of work, each task with its own verification;
- blast radius and risk;
- proof: exact commands and expected result.

A plan step is done when one reasonable thing can be written from it. Do not
leave "handle edge cases" as a step.

## 4. Build

- For a bug, write the failing test first, run it, confirm it fails for the
  expected reason, then fix the code. Do not edit the test to make it pass.
  Editing `backend/tests/`, `backend/eval/` or `backend/data/scenari.json`
  triggers an approval prompt: explain why the contract changes.
- Follow the existing architecture; do not add a new abstraction for one use.
- Do not hand-edit generated artifacts under `backend/data/rag/`. Run
  `make dataset`.
- Do not add a dependency without a reason that survives the review.

## 5. Test

Run the smallest sufficient proof and paste it:

```bash
make test
cd backend && uv run pytest -q tests/test_safety_contract.py
python3 scripts/check_ai_native.py
```

Before a production change, also `make build`. For UI work, check the flow in a
browser: original leaflet visible, citation jumps to the block, disclaimer
present, keyboard and focus work.

## 6. Review

Apply `REVIEW.md`: bugs, security, medical safety, compliance with
`spec.md`/`plan.md`, proof. Findings are ranked; humans approve. If the review
flags the same mistake for the second time, add the rule to `AGENTS.md` or a
skill.

## 7. Deploy

A human authorizes production. Preview deploys are safe. Rollback means
promoting the previous healthy deployment and verifying `/api/rag/status` and
a drug page. Never deploy to production from an agent session without an
explicit release authorization.

## 8. Maintain

An incident, a repeated mistake or a metric outside its band becomes a new
`intent.md`. Add an eval for the incident class so it does not come back.

## Definition of done

- [ ] `intent.md`, `spec.md`, `plan.md` exist and match the diff.
- [ ] Tests were written or updated, and they pass.
- [ ] `make test` output is in the PR.
- [ ] `python3 scripts/check_ai_native.py` passes.
- [ ] Medical content was reviewed with `medical-content-safety`.
- [ ] The PR links the artifacts, states the risk and the rollback.
- [ ] No secret, generated artifact or weakened test is in the diff.

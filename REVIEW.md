# Review instructions

Run these passes on every pull request and tag each finding with its pass.
The author may be an agent; the approval is always human.

## Passes

1. **Bugs** — logic errors, broken edge cases, regressions, state that leaks
   between drugs or sessions.
2. **Security and privacy** — prompt injection, unbounded input, secrets in
   the diff or in logs, unsafe external calls, dependency risk.
3. **Medical safety and grounding** — every health claim traceable to a
   leaflet block or named section; doses exact; warnings intact; red flags
   escalate; disclaimer present. See
   `.opencode/skills/medical-content-safety/SKILL.md`.
4. **Compliance with the change** — the diff matches `spec.md` and `plan.md`
   in `docs/ai-native/<date>-<slug>/`. Flag scope that is not in the plan, and
   ask for `plan.md` to be updated when the implementation deliberately
   departs from it.
5. **Proof** — the PR shows the commands run and their output: `make test`,
   `make build` for UI/deploy changes, `python3 scripts/check_ai_native.py`,
   plus a browser check for user-facing flows.

## What Important means here

Reserve **Important** for findings that would:

- produce a wrong or unsupported health statement, a lost warning, or a
  missing escalation;
- break a user flow, the retrieval fallback, or the cited-source mapping;
- leak data, credentials or internal details;
- make the change impossible to roll back or verify.

Style, naming, formatting and preference are **nits**.

## Cap the nits

Report at most five nits per review; summarize the rest as a count.

## Do not report

- Generated artifacts under `backend/data/rag/` unless they are stale
  relative to their source.
- Anything CI already enforces (Ruff, ESLint, build, tests) unless the fix is
  not obvious from the log.
- Lockfile churn, formatting-only diffs, or dependency bumps with a green CI
  and no behavior change.

## Human gate

Findings do not approve or block on their own. A human code owner approves,
and production deploys need a named release authorization. When a finding is
about medical content, the reviewer must be able to point to the source block;
"looks fine" is not approval.

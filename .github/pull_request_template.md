## What changed

<!-- One paragraph. Link the artifacts. -->

- Intent: `docs/ai-native/<date>-<slug>/intent.md`
- Spec: `docs/ai-native/<date>-<slug>/spec.md`
- Plan: `docs/ai-native/<date>-<slug>/plan.md`

## Verification

<!-- Paste the commands and the relevant output, not a summary. -->

```bash
make test
```

```
<output>
```

For UI changes:

```bash
make build
```

- [ ] Browser check of the touched flow (original leaflet visible, citation
      jumps to the block, disclaimer present, keyboard/focus work).

## Risk and blast radius

<!-- What can break, who is affected, how it is detected. -->

## Medical safety

<!-- Delete this section only if no prompt, content, retrieval chunking or
user-facing copy changed. -->

- [ ] Every health claim maps to a leaflet block or named section.
- [ ] Doses, units and frequencies are exact.
- [ ] Warnings stayed next to their condition; none were softened.
- [ ] Red flags escalate to 112/118.
- [ ] Disclaimer is present on every touched surface.
- [ ] Reviewed with `.opencode/skills/medical-content-safety/SKILL.md`.

## Rollback

<!-- How to undo this. For a deploy: which deployment is promoted back. -->

## Checklist

- [ ] The diff matches `plan.md`, or `plan.md` was updated in this PR.
- [ ] No secret, generated artifact or weakened test is in the diff.
- [ ] `python3 scripts/check_ai_native.py` passes.
- [ ] The code owner has approved; production deploy has a named release
      authorization.

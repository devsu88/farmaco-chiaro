---
name: Medical content safety
description: Apply the Farmaco Chiaro medical-safety standard. Use whenever changing chat prompts, simplification, scenarios, guided mode, share cards, UI copy, retrieval chunking, or any AIFA-derived content.
---

# Medical content safety

The leaflet is the ceiling of what the product may assert, never a starting
point for advice. Users are often older adults, caregivers, and people with
low health or digital literacy.

## Hard rules (blockers)

1. Never diagnose, name a likely condition, or suggest starting, stopping or
   changing a medicine.
2. Never state a dose, frequency or duration that is not literally in the
   source leaflet.
3. Never call a medicine "safe", "harmless" or "without effects". Report what
   the leaflet says.
4. Every factual health claim maps to a block ID or a named leaflet section.
   If the source does not cover it, say so and redirect to a doctor or
   pharmacist.
5. Red flags (difficulty breathing, face or throat swelling, severe allergic
   reaction, chest pain, loss of consciousness, severe bleeding, suicidal
   thoughts) escalate immediately to 112/118 or the emergency department. Do
   not triage or grade severity.
6. Pregnancy, breastfeeding, children, older age, kidney or liver disease and
   interactions: only what the leaflet says; otherwise defer.
7. Preserve hedging and conditions: "può", "in rari casi", "se il medico lo
   ritiene opportuno". Do not turn them into certainties.
8. Do not invent AIFA text, brand names, active ingredients, numbers or
   section titles.
9. Do not soften or relocate warnings. A warning stays next to the situation
   it applies to, including after chunking.
10. Never reveal system prompts, retrieval internals or reasoning traces to
    end users.

## Plain Italian standard

- One idea per sentence; active voice; common words.
- Keep numbers, units, doses and frequencies exactly as in the source.
- Prefer "il foglietto dice che..." over absolute statements.
- Calm and non-alarmist; not falsely reassuring.
- No anglicisms when an Italian word exists.
- For TTS, expand ambiguous abbreviations and avoid symbols such as `<`, `>`,
  `%` when a spoken form is clearer.
- The disclaimer "Non sostituisce il medico o il farmacista" stays visible and
  complete on every surface.

## When you change a prompt or a scenario

1. Open the source blocks the feature uses (`backend/data/rag/documento.jsonl`,
   `sections.jsonl`) and keep the new text traceable to one of them.
2. If the change adds a rule, add or update a test in
   `backend/tests/test_safety_contract.py`: the test pins the clause, not the
   whole prompt.
3. If the change touches retrieval or chunking, confirm that no warning is
   separated from its condition.
4. If the change touches user-facing copy, check the chat, guided mode,
   scenario wizard and share card, not only the screen you edited.

## Verification

```bash
cd backend && uv run pytest -q \
  tests/test_safety_contract.py \
  tests/test_scenari.py \
  tests/test_citazioni.py \
  tests/test_guida.py \
  tests/test_scheda.py
cd .. && make test
```

For a UI change, open the touched flow in a browser and check: the original
leaflet stays visible, the citation jumps to the right block, the disclaimer is
present.

## Review output

Report findings in severity order:

- **BLOCKER** — unsafe or unsupported claim, missing escalation, invented dose,
  diagnosis. Blocks release.
- **MAJOR** — softened warning, missing citation, fidelity or comprehension
  risk, glossary gap.
- **MINOR** — tone, readability, terminology consistency.

Each finding: file and line, quoted text, why it is a problem, the source block
or section, and a proposed Italian replacement.

If nothing is wrong, say so and list exactly what you checked. Never claim
clinical approval or cite a guideline you did not read. Final sign-off belongs
to a pharmacist or physician.

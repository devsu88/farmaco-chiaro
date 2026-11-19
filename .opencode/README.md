# Project subagents

Project-scoped OpenCode agents for Farmaco Chiaro. They encode this repository's
paths, stack, and safety invariants, so they live here rather than in
`~/.config/opencode/agents/`.

## Provenance

Eleven agents are adapted from
[ankitmundada/awesome-opencode-subagents](https://github.com/ankitmundada/awesome-opencode-subagents)
(MIT, commit `e516176`):

| Agent | Source |
|---|---|
| `python-pro` | `02-language-specialists/python-pro.md` |
| `nextjs-developer` | `02-language-specialists/nextjs-developer.md` |
| `react-specialist` | `02-language-specialists/react-specialist.md` |
| `api-designer` | `01-core-development/api-designer.md` |
| `llm-architect` | `05-data-ai/llm-architect.md` |
| `prompt-engineer` | `05-data-ai/prompt-engineer.md` |
| `nlp-engineer` | `05-data-ai/nlp-engineer.md` |
| `accessibility-tester` | `04-quality-security/accessibility-tester.md` |
| `test-automator` | `04-quality-security/test-automator.md` |
| `deployment-engineer` | `03-infrastructure/deployment-engineer.md` |
| `refactoring-specialist` | `06-developer-experience/refactoring-specialist.md` |

`medical-content-guardian` is written for this project; the upstream collection
has no medical-domain agent.

## Adaptations applied

- Frontmatter converted from the deprecated V1 shape (`tools`, `temperature`) to
  OpenCode V2 (`permissions`, `steps`).
- Removed the upstream `Communication Protocol`, fabricated progress and delivery
  blocks, and cross-agent integration lists that referenced agents not installed.
- Added a `## Project context: Farmaco Chiaro` section to every agent.
- Corrected stack claims: Next.js 16 instead of 14, no Edge runtime, `uv` and
  Ruff instead of Poetry and black, no mypy or bandit, Vercel Services instead of
  Kubernetes and generic CI.

The generic parts remain: review the prompt body before trusting an agent on a
task outside this repository's stack.

# Repository Guidelines

## Project Scope

This repository contains ActionGate, a Code Track entry for the SitRep AI Agent
Hackathon. The NeuroGolf workspace is preserved separately at
`/Users/jhkang/code/competitions/neurogolf-2026`; it is not part of this
repository's history. Do not restore or mix NeuroGolf files into this project.

`/Users/jhkang/code/kaggle` is the stable active-competition path and resolves
to this standalone repository. Treat this repository root as the complete
workspace boundary: do not scan or modify sibling repositories under
`/Users/jhkang/code/competitions/` unless the user explicitly requests it.

## Structure

- `handler.py`: ActionGate extraction, evidence audit, scoring, and rendering.
- `app.py`: SitRep FastAPI contract for `/run`, `/test`, and `/health`.
- `sitrep_agent/`: request-signature and OpenAI-compatible LLM helpers.
- `tests/`: deterministic unit and endpoint tests.
- `agent.json`: Marketplace metadata.
- `prompt.txt`: evidence-first system prompt.
- `docs/`: competition decisions, demo scenario, submission draft, and live status.
- `.agents/skills/`: orchestration, submission, and retrospective workflows.

## Development

Use Python 3.12+ and `uv`.

```bash
uv sync
uv run pytest
uv run ruff check .
uv run uvicorn app:app --port 9000
bash scripts/smoke-test.sh
uv run python scripts/preflight_submission.py
```

## Competition Harness

Use the repo-local `orchestration` skill for any non-trivial product, judging,
or deployment decision. Start from the live deadline and submission state, then
rank work by expected rubric gain per hour. Keep at least one bounded exploration
lane active until the entry has a tested differentiator; do not let repeated
polish consume every loop.

Use subagents for distinct independent roles when available: rubric critic,
adversarial reliability reviewer, UX reviewer, or deployment/submission auditor.
The main agent owns integration and final validation. Every serious loop must
leave one concrete artifact such as a test, product change, evaluation result,
deployment proof, demo asset, or updated submission record.

Use `submission` before external publishing and `retrospective` after failed
tests, deployment friction, judge feedback, or repeated manual work. A repeated
step belongs in a script or skill; a durable decision belongs in `docs/`.

## Quality Rules

Treat business impact, output reliability, and Marketplace UX as primary scoring
surfaces. Never infer an owner from the attendee list. Confirmed facts require an
exact source quote; suggestions must remain visibly proposed or inferred. Add a
regression test for every output or evidence-handling change.

Keep secrets in `.env` only. Never commit SitRep signing secrets or LLM API keys.
Before publishing, verify the public repository is MIT licensed, the deployed
endpoint checks signatures, and the Kaggle writeup stays under 1,000 words.

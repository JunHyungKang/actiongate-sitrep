# Repository Guidelines

## Project Scope

This branch contains ActionGate, a Code Track entry for the SitRep AI Agent
Hackathon. The archived NeuroGolf workspace is preserved on
`archive/neurogolf-2026` and the `neurogolf-2026-final` tag. Do not restore or
mix NeuroGolf files into this branch.

## Structure

- `handler.py`: ActionGate extraction, evidence audit, scoring, and rendering.
- `app.py`: SitRep FastAPI contract for `/run`, `/test`, and `/health`.
- `sitrep_agent/`: request-signature and OpenAI-compatible LLM helpers.
- `tests/`: deterministic unit and endpoint tests.
- `agent.json`: Marketplace metadata.
- `prompt.txt`: evidence-first system prompt.
- `docs/`: competition decisions, demo scenario, and submission draft.

## Development

Use Python 3.12+ and `uv`.

```bash
uv sync
uv run pytest
uv run ruff check .
uv run uvicorn app:app --port 9000
bash scripts/smoke-test.sh
```

## Quality Rules

Treat business impact, output reliability, and Marketplace UX as primary scoring
surfaces. Never infer an owner from the attendee list. Confirmed facts require an
exact source quote; suggestions must remain visibly proposed or inferred. Add a
regression test for every output or evidence-handling change.

Keep secrets in `.env` only. Never commit SitRep signing secrets or LLM API keys.
Before publishing, verify the public repository is MIT licensed, the deployed
endpoint checks signatures, and the Kaggle writeup stays under 1,000 words.

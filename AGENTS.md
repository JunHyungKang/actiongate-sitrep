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

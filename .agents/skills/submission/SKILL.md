---
name: submission
description: Verify and record ActionGate deployment, SitRep Marketplace publication, Kaggle writeup, and public repository requirements.
---

# ActionGate Submission

## Preflight

Run:

```bash
uv run python scripts/preflight_submission.py
uv run pytest
uv run ruff check .
bash scripts/smoke-test.sh
```

Then verify live requirements that local code cannot prove:

- public MIT repository and required starter-repository star
- deployed `/health`, valid-signature request, and invalid-signature rejection
- one ambiguous Studio case returns HOLD and one complete case returns PROCEED
- Marketplace listing is published and its link is available
- Kaggle writeup is at most 1,000 words and includes the required links

## Evidence Record

For every external attempt, record timestamp, commit SHA, endpoint or listing
URL, result, blocker, and next action in `docs/submission-status.md`. Never store
tokens, signing secrets, OTPs, or API keys.

The main agent owns final publication and must not infer success from a local
test. A live URL, Marketplace state, or submission confirmation is required.

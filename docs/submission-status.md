# Submission Status

Last verified: 2026-07-17 KST

## Live Snapshot

- Kaggle deadline: 2026-07-20 11:00 KST
- Kaggle entrants: 4 teams; current account entry state: not joined
- Deployed endpoint: <https://sitrep-agent.onrender.com>
- Endpoint health: `200 {"ok":true}`
- Marketplace listing: <https://app.joinsitrep.com/dashboard/marketplace/actiongate--450b1ac1-84b5-415b-9101-5660fc31c79b>
- Marketplace state: published, 1 install, 0 runs
- Deployed commit: `076d209`

## Complete

- Public repository: <https://github.com/JunHyungKang/actiongate-sitrep>
- Repository visibility: public
- License: MIT
- Required `SitRepAI/AgentStarterKit` star: verified
- Marketplace listing: published
- Render deployment: free plan, healthy
- SitRep signing secret: regenerated and synchronized to Render on 2026-07-17
- Signed Studio smoke tests: 3/3 passed against the live endpoint
- Studio result preview: Markdown-first output verified with a visible `HOLD` decision
- Explicit Studio HOLD case: `20/100`, `RED - BLOCKED`, `HOLD`, `1/6`
- Explicit Studio PROCEED case: `100/100`, `GREEN - READY`, `PROCEED`, `6/6`
- Public LLM usage guard: explicit complete contracts skip the LLM; remaining calls are bounded to 12,000 input characters and 50 calls per UTC day per service process
- Local preflight: passing
- Tests: 44 passing, including a real HMAC request, semantic evidence checks,
  malformed-payload handling, and adversarial evaluation checks

## Pending

- Join the Kaggle hackathon, attach the Marketplace and repository URLs, and submit the final writeup.

Do not record credentials, OTPs, signing secrets, or API keys in this file.

---
name: retrospective
description: Convert ActionGate failures, repeated manual work, and judge evidence into durable harness improvements.
---

# ActionGate Retrospective

Use this skill after a failed test or deployment, external feedback, a repeated
agent mistake, or two similar manual steps.

1. State the observed evidence and impact. Keep hypotheses visibly uncertain.
2. Identify whether the failure came from selection, implementation,
   validation, deployment, UX, or submission state.
3. Put the smallest durable fix in the correct surface:
   - behavior rule -> `AGENTS.md`
   - repeatable workflow -> `.agents/skills/`
   - repeatable check -> `scripts/` plus tests
   - product or competition decision -> `docs/`
4. Update the selection rule or stop condition when the lesson changes what
   should be attempted next. A prose note alone is insufficient for a recurring
   failure.
5. Verify the changed harness and name the next concrete artifact.

Self-improvement can reinforce a local optimum. Check explicitly whether recent
loops only polished the same solution. If so, schedule a bounded exploration
with a different hypothesis and observable acceptance criteria.

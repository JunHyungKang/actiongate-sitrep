---
name: orchestration
description: Coordinate rubric-first ActionGate work, bounded exploration, independent reviews, and concrete competition artifacts.
---

# ActionGate Orchestration

## Start From Current State

Before substantial work, confirm the deadline, SitRep publication state,
deployed endpoint health, repository visibility, and remaining submission
requirements. Do not trust an old chat summary for live state.

## Choose The Next Artifact

Rank candidates by expected rubric gain per hour across business impact, agent
quality, UX, innovation, execution, and documentation. Prefer evidence that a
judge can observe in the agent, demo, tests, or writeup.

Maintain two lanes:

- **Exploit:** remove the largest known blocker or strengthen the weakest
  high-value rubric surface.
- **Explore:** spend roughly one in four non-critical loops on a time-boxed new
  differentiator, adversarial scenario, or workflow hypothesis.

An exploration must define a hypothesis, time limit, observable success signal,
and keep/stop decision. Shipping and submission blockers override the quota near
the deadline, but record the skipped exploration debt.

## Use Independent Roles

For scoring-surface changes, use subagents when available and assign distinct
roles: rubric critic, adversarial reliability reviewer, UX reviewer, or
deployment/submission auditor. Do not ask several agents the same broad
question. The main agent reviews their evidence, integrates changes, runs tests,
and owns external actions.

## Close The Loop

Each loop must produce one concrete artifact: code and regression test,
evaluation result, deployment proof, demo asset, submission update, or harness
improvement. If an approach fails, record the stop reason and invoke the
`retrospective` skill so the next loop does not rediscover it.

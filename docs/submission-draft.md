# ActionGate: Stop Ambiguous Meeting Actions Before They Become Rework

## Inspiration

Meeting assistants are good at finding action items, but an extracted action is
not necessarily safe to execute. Phrases such as "follow up next week" often lack
an owner, exact deadline, deliverable, or definition of done. A downstream agent
can turn that ambiguity into confident but expensive mistakes.

## What It Does

ActionGate is an ambiguity firewall and pre-execution contract validator. For
one SitRep action it:

- extracts only facts backed by exact source evidence;
- checks owner, deadline, deliverables, success criteria, and dependencies;
- assigns a RED, YELLOW, or GREEN readiness gate;
- separates confirmed facts from inferred risks and proposed steps;
- generates the smallest set of questions needed to unblock execution;
- returns a copy-ready clarification request or a ready-to-handoff decision.

Attendance is never treated as ownership, and relative phrases such as "next
week" are never promoted to precise deadlines.

## How We Built It

The Code Track agent uses one constrained LLM pass to extract a typed execution
contract. A deterministic Python policy engine then rejects every confirmed fact
whose value and evidence do not appear in the task or meeting summary. The model
cannot override the owner, deadline, or readiness gates. The final artifacts are
rendered from the audited structure, not directly from free text: a detailed
Markdown contract and a decision-first HTML approval packet for Marketplace users.

## Challenges

The hard part was balancing usefulness and refusal. Blocking everything is safe
but unhelpful; generating a polished plan is useful but can hide assumptions.
ActionGate resolves this by keeping proposed next steps visible while reserving
the confirmed contract and GREEN status for source-supported commitments.

## Accomplishments

- deterministic evidence and ownership gates;
- explicit handling of vague deadlines;
- graceful fallback when structured model output fails;
- regression tests for the main unsafe-execution cases;
- no required third-party integration beyond an OpenAI-compatible model.

## What We Learned

Agent reliability depends as much on the execution boundary as on model quality.
A small validation layer can create more business value than another broad
generation workflow by preventing ambiguous work from entering automation.

## What's Next

Future versions can post approved contracts to GitHub, Jira, or Linear and learn
which missing commitments most often cause rework, while keeping every external
action behind explicit human approval.

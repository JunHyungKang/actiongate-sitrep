# ActionGate: Stop Ambiguous Meeting Actions Before They Become Rework

**Live agent:** [ActionGate on the SitRep Marketplace](https://app.joinsitrep.com/dashboard/marketplace/actiongate--450b1ac1-84b5-415b-9101-5660fc31c79b)<br>
**Source:** [Public MIT-licensed GitHub repository](https://github.com/JunHyungKang/actiongate-sitrep)

## Inspiration

Meeting assistants are good at finding action items, but an extracted action is
not necessarily safe to execute. Phrases such as "follow up next week" often lack
an owner, exact deadline, deliverable, or definition of done. A downstream agent
can turn that ambiguity into confident but expensive mistakes.

## What It Does

ActionGate is an ambiguity firewall and pre-execution contract validator. For
one SitRep action it:

- confirms only facts backed by exact source evidence;
- checks owner, deadline, deliverables, success criteria, and dependencies;
- assigns a RED, YELLOW, or GREEN readiness gate;
- separates confirmed facts from inferred risks and proposed steps;
- generates a focused question for each missing execution commitment;
- returns a copy-ready clarification request or a ready-to-handoff decision.

Attendance is never treated as ownership, and relative phrases such as "next
week" are never promoted to precise deadlines.

## How We Built It

The Code Track agent combines a constrained LLM pass with a deterministic
extractor for explicitly labeled commitments. A Python policy engine then
rejects every confirmed fact whose value and evidence do not appear in the task
or meeting summary. The model cannot override the owner, deadline, or readiness
gates, and provider failure cannot block a fully explicit labeled contract. The final
artifacts are rendered from the audited structure, not directly from free text:
a detailed Markdown contract and a decision-first HTML approval packet.

## Challenges

The hard part was balancing usefulness and refusal. Blocking everything is safe
but unhelpful; generating a polished plan is useful but can hide assumptions.
ActionGate resolves this by keeping proposed next steps visible while reserving
the confirmed contract and GREEN status for source-supported commitments.

## Accomplishments

- deterministic evidence and ownership gates;
- an eight-case synthetic policy suite that reduced false-PROCEED decisions
  from five to zero versus a presence-only baseline;
- a six-case artifact-level scenario suite with 6/6 decisions correct, zero
  unsupported confirmations, and 9/9 missing-field questions recovered;
- explicit handling of vague deadlines;
- provider-independent recovery of explicit complete contracts;
- 46 regression tests covering evidence validation, ownership, deadlines,
  provider failure, signed requests, output safety, and usage limits;
- no required third-party integration beyond an OpenAI-compatible model.

In signed SitRep Studio runs against the deployed agent, an ambiguous action
returned `HOLD` at `20/100`, while a fully supported contract returned
`PROCEED` at `100/100`. These are live contract-completeness results; the
eight-case false-PROCEED comparison above is a separate deterministic policy
evaluation rather than an end-to-end model benchmark. The six-case scenario
suite separately validates complete Markdown and HTML artifacts with controlled
candidate extractions.

## What We Learned

Agent reliability depends as much on the execution boundary as on model quality.
A small validation layer can create more business value than another broad
generation workflow by preventing ambiguous work from entering automation.

## What's Next

Future versions can post approved contracts to GitHub, Jira, or Linear and learn
which missing commitments most often cause rework, while keeping every external
action behind explicit human approval.

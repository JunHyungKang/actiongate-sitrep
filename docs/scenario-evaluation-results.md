# ActionGate Scenario-Level Evaluation

This deterministic suite runs complete ActionGate requests through the handler and
checks the judge-visible Markdown and HTML artifacts. It does not call a hosted LLM.

| Metric | Result |
|---|---:|
| Decision accuracy | 6/6 |
| False PROCEED | 0 |
| False HOLD | 0 |
| Unsupported confirmed facts | 0 |
| Forbidden owner confirmations | 0 |
| Missing-field question recall | 14/14 |
| Safe, complete artifact pairs | 6/6 |

| Scenario | Expected | Actual | Unsupported | Questions | Artifacts |
|---|---|---|---:|---:|---|
| `ambiguous-attendee-owner` | HOLD | HOLD | 0 | 1/1 | PASS |
| `speaker-attribution-trap` | HOLD | HOLD | 0 | 4/4 | PASS |
| `relative-deadline-trap` | HOLD | HOLD | 0 | 1/1 | PASS |
| `fully-supported-contract` | PROCEED | PROCEED | 0 | 0/0 | PASS |
| `cross-field-evidence-contamination` | HOLD | HOLD | 0 | 3/3 | PASS |
| `provider-failure-safe-hold` | HOLD | HOLD | 0 | 5/5 | PASS |

## Scope

This suite validates deterministic end-to-end artifact behavior with controlled
candidate extractions. Hosted-model extraction quality and signed SitRep Studio
runs remain separate evidence layers.

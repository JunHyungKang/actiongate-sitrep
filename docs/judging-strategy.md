# ActionGate Judging Strategy

## Product Thesis

Meeting automation fails when an extracted action looks executable but still
lacks a confirmed owner, date, deliverable, success condition, or dependency.
ActionGate is the control point between extraction and execution. It returns a
useful approval packet instead of silently filling those gaps.

## Rubric Map

| Surface | Points | Evidence in the product |
|---|---:|---|
| Business Impact | 30 | Prevents rework and unsafe handoffs; creates a copy-ready clarification request. |
| Agent Quality | 25 | Exact-quote audit, deterministic field gates, attendee-owner protection, and safe fallback. |
| User Experience | 15 | Immediate HOLD/PROCEED decision, readiness score, verified contract, and polished HTML. |
| Innovation | 15 | Treats ambiguity as an execution-control problem rather than another generation prompt. |
| Execution | 10 | Typed extraction, deterministic policy engine, signature verification, safe fallback, and regression tests. |
| Documentation | 5 | Public MIT repository, two-minute demo, architecture explanation, and reproducible local setup. |

## Submission Gate

Before publishing, verify an ambiguous example remains HOLD, a fully specified
example reaches PROCEED, attendee names cannot become owners without source
evidence, relative dates remain blocked, HTML contains no executable script, and
the deployed endpoint rejects invalid signatures.

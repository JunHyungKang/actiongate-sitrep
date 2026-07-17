# ActionGate Adversarial Evaluation

This deterministic suite isolates the policy layer: both systems receive the same
candidate extraction, while ActionGate additionally audits ownership, deadline, and
risk evidence before allowing execution.

| System | Correct | False PROCEED | False HOLD | Risk confirmation errors |
|---|---:|---:|---:|---:|
| Presence-only baseline | 3/8 | 5 | 0 | 1 |
| ActionGate | 8/8 | 0 | 0 | 0 |

| Case | Expected | Presence-only | ActionGate |
|---|---|---|---|
| `attendee-is-not-owner` | HOLD | PROCEED | HOLD |
| `speaker-is-not-reported-owner` | HOLD | PROCEED | HOLD |
| `date-only-is-not-deadline` | HOLD | PROCEED | HOLD |
| `invalid-calendar-date` | HOLD | PROCEED | HOLD |
| `non-deadline-date-context` | HOLD | PROCEED | HOLD |
| `fully-supported-contract` | PROCEED | PROCEED | PROCEED |
| `missing-definition-of-done` | HOLD | HOLD | HOLD |
| `unrelated-risk-evidence` | PROCEED | PROCEED | PROCEED |

## Scope

These are policy-layer regression cases, not a claim about a particular hosted LLM's
extraction accuracy. Live SitRep HOLD and PROCEED runs are tracked separately in
`docs/submission-status.md`.

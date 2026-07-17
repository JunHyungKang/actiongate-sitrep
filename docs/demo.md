# ActionGate Demo

![ActionGate HOLD to PROCEED comparison](actiongate-comparison.png)

## Input

**Action task:** Follow up with Acme about the pilot next week.

**Meeting summary:** Acme wants a security review before expanding the pilot.
Priya mentioned the SOC2 packet may be outdated. Jordan said legal needs two
business days. The customer asked for a revised rollout plan before their Friday
steering meeting.

**Attendees:** Maya Chen, Priya Shah, Jordan Lee, Chris Park from Acme.

## Expected Behavior

ActionGate must not assign the action to Maya merely because she appears first.
It must not convert "next week" or "Friday" into a precise deadline. Any fact it
does confirm must preserve an exact quote from the supplied task or meeting
summary; unsupported model output must be discarded.

The result should be RED or YELLOW and ask:

1. Who owns the Acme follow-up?
2. What exact artifact must be sent?
3. What is the calendar deadline and timezone?
4. Who approves the SOC2 and legal content?
5. What outcome marks the follow-up complete?

## Two-Minute Demo Story

1. Show a generic model confidently assigning Maya and inventing Monday.
2. Run the same action through ActionGate.
3. Highlight the readiness gate and rejected assumptions.
4. Show exact evidence beside each confirmed fact.
5. Update the source input with a named owner, `2026-07-20 17:00 KST`, the exact
   rollout-plan deliverable, approval criteria, and dependencies, then rerun to
   demonstrate that the fully supported contract reaches GREEN.

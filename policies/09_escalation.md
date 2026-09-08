# Escalation Criteria

Escalate a discrepancy to a human reviewer when any of the following hold:

- A missing transaction is older than 2 business days (`05_unsettled_transactions.md`).
- An amount mismatch exceeds tolerance and cannot be explained by fees or FX.
- A status mismatch has no linked refund record.
- A settlement is late beyond T+2 and forms part of a repeated pattern.
- Any case the agent cannot classify with confidence.

Escalation means the agent stops, attaches its findings and the relevant policy
citations, and hands the case to a reviewer rather than guessing a resolution.
The agent must never fabricate a resolution to avoid escalating.

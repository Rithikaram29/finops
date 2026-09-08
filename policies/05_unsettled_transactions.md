# Unsettled (Missing) Transactions

A captured ledger transaction with **no** corresponding settlement row is an
**missing_in_settlement** discrepancy.

Resolution:
1. Confirm the transaction is genuinely captured and not voided.
2. Flag it as **pending settlement**.
3. If the transaction is **2 business days old or less**, allow it to remain
   pending — settlement may still arrive.
4. If it is **older than 2 business days**, escalate per `09_escalation.md`.

Do not create a synthetic settlement to close the gap.

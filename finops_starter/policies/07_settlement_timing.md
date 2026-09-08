# Settlement Timing

Settlements are expected to complete within **T+2** (two business days of the
transaction date). Settlement within this window is normal and requires **no
action**, even if it lands on a different calendar day than the transaction.

A settlement completing **after T+2** is a **timing_difference** discrepancy.
Flag it, record the delay reason where known, and monitor for a pattern of late
settlements from the same gateway, which is escalated per `09_escalation.md`.
Timing differences alone do not change amounts owed.

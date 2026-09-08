# Status Reconciliation (Refund vs Capture)

Ledger status and settlement status must be consistent. The normal pairing is
ledger `captured` with settlement `settled`.

A settlement marked **refunded** against a ledger entry still marked **captured**
is a **status_mismatch** discrepancy. This is expected only when a genuine refund
was issued.

Resolution:
1. Look for a **linked refund record** explaining the reversal.
2. If a valid refund record exists, update the ledger status to reflect it.
3. If **no** refund record exists, escalate per `09_escalation.md` — an
   unexplained refund may indicate an error or fraud.

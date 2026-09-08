# Duplicate Settlements

When two or more settlement rows reference the same `txn_ref`, the transaction has
a **duplicate_settlement** discrepancy. Duplicate settlements risk double-paying a
merchant and must be corrected.

Resolution:
1. Identify the settlements sharing the `txn_ref`.
2. **Retain the earliest** settlement by `settled_at`.
3. Mark the later settlement(s) for **reversal**.
4. Adjust the ledger so the transaction reflects a single settlement.
5. Route the reversal for human approval before finalising.

# Reconciliation Overview

Reconciliation is the process of matching two independent records of the same
financial activity and resolving any differences between them. In this system we
reconcile the **internal ledger** (`transactions.csv`, "our records") against the
**settlement report** (`settlement.csv`, "the gateway/bank records").

A transaction is considered **matched** when a settlement row references it
(`txn_ref == txn_id`), the amounts agree once fees are accounted for, the
settlement falls within the accepted timing window, and the statuses are
consistent.

Anything that fails one of those checks is a **discrepancy** and must be
classified, explained with reference to the relevant policy, and either resolved
automatically (where policy allows) or escalated to a human. No discrepancy is
marked resolved without human sign-off (see `10_approval_signoff.md`).

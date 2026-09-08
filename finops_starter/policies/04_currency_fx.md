# Currency & FX Handling

Most transactions are in INR. Some are in USD or EUR. Ledger and settlement must
be reconciled in the **same currency**; a settlement whose currency differs from
its ledger entry must be converted using the transaction-date reference rate
before comparison.

Small residual differences after conversion fall under the standard amount
tolerance (`02_amount_tolerances.md`). Large post-conversion differences are an
**amount_mismatch** and are flagged for manual review. FX rate disputes are
escalated per `09_escalation.md`.

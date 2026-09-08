# Amount Matching & Tolerances

For a matched pair, the settled amount should equal the transaction amount minus
the processing fee:

    settled_amount == amount - fee

A residual difference of up to **1.00 (one rupee)** in absolute value is treated
as a rounding artefact and is **not** a discrepancy. Do not flag differences
within tolerance.

If the absolute difference exceeds the tolerance **and** is not explained by a
recorded fee (`03_fees_and_charges.md`) or a currency conversion
(`04_currency_fx.md`), classify the pair as an **amount_mismatch** and flag it for
manual review. Never auto-adjust a ledger amount to force a match.

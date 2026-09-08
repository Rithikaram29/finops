# Fees & Charges

Gateway processing fees are expected on every settlement and typically range from
1.5% to 2.5% of the transaction amount. The fee is reported in the settlement's
`fee` field and already deducted from `settled_amount`.

When checking amounts, always reconstruct the gross value as
`settled_amount + fee` before comparing to the ledger `amount`. A settlement that
appears "short" purely because of its fee is a **correct match**, not a
discrepancy. Only treat an amount difference as a mismatch when it remains after
fees are added back and exceeds tolerance (`02_amount_tolerances.md`).

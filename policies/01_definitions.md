# Definitions & Glossary

- **Ledger / transaction:** an entry in our internal records that a payment was
  captured. Identified by `txn_id`.
- **Settlement:** the gateway or bank confirmation that funds moved, identified by
  `settlement_id` and linked to a transaction via `txn_ref`.
- **Fee:** the processing charge deducted by the gateway. Expected relationship:
  `settled_amount = amount - fee`.
- **Captured:** funds authorised and taken from the customer (ledger status).
- **Settled:** funds transferred to the merchant account (settlement status).
- **Refunded:** funds returned to the customer.
- **T+N:** settlement occurring N business days after the transaction date.
- **Tolerance:** the maximum amount difference treated as a rounding artefact
  rather than a real mismatch.

# FinOps Agent — starter data + policy corpus

Generated starting point for the reconciliation flagship.

## Layout
    generate_data.py      # seeded synthetic data generator (stdlib only)
    data/
      transactions.csv    # internal ledger  (300 rows)
      settlement.csv      # settlement report (299 rows)
      ground_truth.json   # 22 injected discrepancies == your eval set
    policies/             # 11 markdown SOP docs == your RAG corpus

## Regenerate the data
    python generate_data.py

Deterministic (SEED=42): re-running produces identical files.

## Next steps
1. Read data/ground_truth.json and the policies/ — make sure each expected
   resolution is backed by its policy_ref doc.
2. Build the deterministic tools (match, detect, calculate) against this data.
3. Later: RAG over policies/, then the LangGraph agent loop.

# FinOps Agent

Reconciliation agent for fintech settlement data: matches an internal ledger
against a settlement report, classifies discrepancies deterministically, and
grounds explanations in a policy corpus via RAG.

## Layout
    generate_data.py   # seeded synthetic data generator (stdlib only)
    tools.py           # deterministic matching + discrepancy detection (the agent's tool)
    policy_rag.py       # BM25 + dense hybrid search over policies/ (the agent's other tool)
    data/
      transactions.csv  # internal ledger
      settlement.csv     # settlement report
      ground_truth.json  # injected discrepancies == eval set
    policies/           # markdown SOP docs == RAG corpus
    tests/               # unit + eval tests for tools.py

## Regenerate the data
    python generate_data.py

Deterministic (SEED=42): re-running produces identical files.

## Run tests
    python3 -m unittest discover tests -v

## Next steps
1. Read data/ground_truth.json and policies/ — confirm each expected
   resolution is backed by its policy_ref doc.
2. Wire a real embedder into policy_rag.py (LocalEmbedder or an API embedder)
   in place of the offline StubEmbedder.
3. Build the LangGraph agent loop: reconcile() -> search_policy() -> LLM writes
   the cited explanation.

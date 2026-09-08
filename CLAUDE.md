# finops

Reconciliation agent: matches ledger vs settlement data, flags discrepancies, explains them via RAG over `policies/`.

- `tools.py` — deterministic matching/detection (`reconcile()`). No LLM calls here; keep it that way — financial logic must not hallucinate.
- `policy_rag.py` — hybrid BM25/dense search over `policies/` (`search_policy()`). Retrieval only, no LLM calls.
- `generate_data.py` — regenerates `data/*` deterministically (SEED=42). Re-run after changing discrepancy injection logic.
- `tests/` — run with `python3 -m unittest discover tests -v` before committing changes to `tools.py`.

The agent loop (LLM) is the only layer that should call an LLM: it calls `reconcile()` and `search_policy()`, then writes the cited explanation.

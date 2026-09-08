"""
matching.py
-----------
Deterministic reconciliation core for the FinOps Agent.

Two PURE functions (no LLM anywhere inside):
    match_transactions(...)   -> pairs ledger & settlement rows by txn_ref into "cases"
    detect_discrepancies(...) -> classifies each case into a discrepancy type

reconcile(...) just composes them. That composed function is the SINGLE tool the
agent calls. The agent's own (LLM) job comes later: for each discrepancy returned
here, retrieve the relevant policy (RAG) and compose an explanation + proposed fix.

Why deterministic? Whether two amounts match, or a settlement is late, are facts.
Letting a model decide them invites hallucination into financial logic. So the
tool decides WHAT is wrong; the agent only explains WHAT TO DO about it.
"""

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

TOLERANCE = 1.00   # rupee tolerance for amount matching  -> policies/02_amount_tolerances.md
T_PLUS = 2         # acceptable settlement window in days  -> policies/07_settlement_timing.md


def _date(s):
    return datetime.fromisoformat(s).date()


# --------------------------------------------------------------------------
# Step 1: MATCH  (pure structural pairing -- no judgement yet)
# --------------------------------------------------------------------------
def match_transactions(transactions, settlements):
    """
    Link records by txn_ref into one 'case' per txn_id seen in either file:
        {"txn_id", "ledger": row|None, "settlements": [rows...]}
    Missing -> settlements is empty. Duplicate -> len(settlements) > 1.
    Orphan  -> ledger is None.
    """
    print("entering match_transactions")
    cases = {}
    for t in transactions:
        cases.setdefault(t["txn_id"], {"txn_id": t["txn_id"], "ledger": None, "settlements": []})
        cases[t["txn_id"]]["ledger"] = t
    for s in settlements:
        ref = s["txn_ref"]
        cases.setdefault(ref, {"txn_id": ref, "ledger": None, "settlements": []})
        cases[ref]["settlements"].append(s)
    return list(cases.values())


# --------------------------------------------------------------------------
# Step 2: DETECT  (classify each case; explicit precedence for multi-issue rows)
# --------------------------------------------------------------------------
def detect_discrepancies(cases, tolerance=TOLERANCE, t_plus=T_PLUS):
    """
    Return only the problematic cases, each as:
        {"txn_id", "discrepancy_type", "evidence": {...}}
    'evidence' carries the numbers that triggered the flag -- the agent hands
    these to the LLM later so the explanation is grounded in real values.
    """
    print("entering detect_discrepancies")
    out = []
    for c in cases:
        led, stls = c["ledger"], c["settlements"]

        # orphan: a settlement with no ledger entry
        if led is None:
            out.append(_d(c, "orphan_settlement", {"settlement_count": len(stls)}))
            continue

        # missing: a captured ledger entry with no settlement
        if not stls:
            out.append(_d(c, "missing_in_settlement",
                          {"ledger_amount": led["amount"], "ledger_status": led["status"]}))
            continue

        # duplicate: more than one settlement for the same txn
        if len(stls) > 1:
            out.append(_d(c, "duplicate_settlement",
                          {"settlement_count": len(stls),
                           "settlement_ids": [s["settlement_id"] for s in stls]}))
            continue

        s = stls[0]

        # status mismatch: e.g. settlement refunded while ledger still captured
        if led["status"] == "captured" and s["status"] != "settled":
            out.append(_d(c, "status_mismatch",
                          {"ledger_status": led["status"], "settlement_status": s["status"]}))
            continue

        # amount mismatch: reconstruct gross (settled + fee), compare to ledger
        gross = round(float(s["settled_amount"]) + float(s["fee"]), 2)
        diff = round(float(led["amount"]) - gross, 2)
        if abs(diff) > tolerance:
            out.append(_d(c, "amount_mismatch",
                          {"ledger_amount": led["amount"], "settled_amount": s["settled_amount"],
                           "fee": s["fee"], "reconstructed_gross": f"{gross:.2f}", "diff": f"{diff:.2f}"}))
            continue

        # timing: settled beyond the T+N window
        days = (_date(s["settled_at"]) - _date(led["timestamp"])).days
        if days > t_plus:
            out.append(_d(c, "timing_difference",
                          {"txn_date": led["timestamp"][:10], "settled_date": s["settled_at"][:10],
                           "days_late": days}))
            continue

        # else: clean match -> not reported
    return out


def _d(case, dtype, evidence):
    return {"txn_id": case["txn_id"], "discrepancy_type": dtype, "evidence": evidence}


# --------------------------------------------------------------------------
# The single deterministic TOOL the agent calls
# --------------------------------------------------------------------------
def reconcile(transactions, settlements):
    return detect_discrepancies(match_transactions(transactions, settlements))


# --------------------------------------------------------------------------
# Self-test against the generated data + ground truth
# --------------------------------------------------------------------------
if __name__ == "__main__":
    data = Path(__file__).parent / "data"
    txns = list(csv.DictReader(open(data / "transactions.csv")))
    stls = list(csv.DictReader(open(data / "settlement.csv")))
    truth = json.load(open(data / "ground_truth.json"))

    found = reconcile(txns, stls)
    found_map = {d["txn_id"]: d["discrepancy_type"] for d in found}
    truth_map = {g["txn_id"]: g["discrepancy_type"] for g in truth}

    tp = set(truth_map) & set(found_map)
    missed = set(truth_map) - set(found_map)
    extra = set(found_map) - set(truth_map)
    type_ok = sum(1 for i in tp if found_map[i] == truth_map[i])

    precision = len(tp) / len(found_map) if found_map else 0
    recall = len(tp) / len(truth_map) if truth_map else 0

    print(f"detected {len(found_map)}   truth {len(truth_map)}")
    print(f"true positives {len(tp)}   missed {len(missed)}   false positives {len(extra)}")
    print(f"type correct on matches {type_ok}/{len(tp)}")
    print(f"precision {precision:.3f}   recall {recall:.3f}")
    print("by type:", dict(Counter(d['discrepancy_type'] for d in found)))
    if missed: print("MISSED:", missed)
    if extra:  print("FALSE POSITIVES:", extra)

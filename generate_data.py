"""
generate_data.py
-----------------
Generates a synthetic reconciliation dataset for the FinOps Agent flagship.

Outputs (into ./data, next to this script):
  - transactions.csv   -> internal ledger  (the "our records" side)
  - settlement.csv     -> gateway/bank settlement report (the "their records" side)
  - ground_truth.json  -> every discrepancy we deliberately injected == your eval set

Design notes (worth reading once):
  * CLEAN rows are perfectly matched: settled_amount = amount - fee, settled same day.
    A naive matcher that compares `amount` to `settled_amount` directly will WRONGLY
    flag every clean row -> so the clean rows are your false-positive test. The agent
    has to understand fees.
  * We inject 5 discrepancy types and record each in ground_truth.json.
  * We ALSO add a few "within-tolerance" noise rows that must NOT be flagged.
  * Everything is SEEDED. Re-running produces byte-identical files. That reproducibility
    is half of what "rigor" means to an interviewer.

Standard library only -> no pip install needed.
Run:  python generate_data.py
"""

import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
SEED = 42
random.seed(SEED)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

N_CLEAN = 300                       # cleanly-matched pairs before we inject problems
BASE_START = datetime(2025, 1, 1)   # transactions span ~30 days from here
TOLERANCE = 1.00                    # rupee tolerance for amount matching (see policies)

MERCHANTS = [
    "Flipkart", "Amazon", "Swiggy", "Zomato", "Uber",
    "BigBasket", "Myntra", "BookMyShow", "Ola", "PhonePe Store",
]
# Mostly INR, a little USD/EUR so the FX policy has a reason to exist.
CURRENCIES = ["INR", "INR", "INR", "INR", "INR", "INR", "USD", "EUR"]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def random_timestamp(days_span=30):
    return BASE_START + timedelta(
        days=random.randint(0, days_span),
        seconds=random.randint(0, 86399),
    )


def money(x):
    """Format a float as a 2-decimal string for clean CSV output."""
    return f"{x:.2f}"


# --------------------------------------------------------------------------
# 1. Build perfectly-matched clean pairs
# --------------------------------------------------------------------------
transactions = []   # ledger rows
settlements = []     # settlement rows
by_txn = {}          # txn_id -> its settlement row (for easy mutation later)

for i in range(1, N_CLEAN + 1):
    txn_id = f"TXN{i:05d}"
    ts = random_timestamp()
    amount = round(random.uniform(100, 10000), 2)
    currency = random.choice(CURRENCIES)
    merchant = random.choice(MERCHANTS)

    fee = round(amount * random.uniform(0.015, 0.025), 2)   # ~1.5-2.5% processing fee
    settled_amount = round(amount - fee, 2)
    settled_at = ts + timedelta(hours=random.randint(1, 10))  # same day

    txn = {
        "txn_id": txn_id,
        "timestamp": ts.isoformat(),
        "amount": money(amount),
        "currency": currency,
        "merchant": merchant,
        "status": "captured",
    }
    stl = {
        "settlement_id": f"STL{i:05d}",
        "txn_ref": txn_id,
        "settled_amount": money(settled_amount),
        "settled_at": settled_at.isoformat(),
        "fee": money(fee),
        "status": "settled",
    }
    transactions.append(txn)
    settlements.append(stl)
    by_txn[txn_id] = stl


# --------------------------------------------------------------------------
# 2. Pick disjoint transactions to corrupt (so no row gets two problems)
# --------------------------------------------------------------------------
pool = list(range(N_CLEAN))
random.shuffle(pool)
_cursor = 0


def take(n):
    """Grab the next n distinct transaction indices from the shuffled pool."""
    global _cursor
    chunk = pool[_cursor:_cursor + n]
    _cursor += n
    return chunk


ground_truth = []


def record(txn_id, dtype, resolution, policy_ref):
    ground_truth.append({
        "txn_id": txn_id,
        "discrepancy_type": dtype,
        "expected_resolution": resolution,
        "policy_ref": policy_ref,
    })


# --- Type 1: missing_in_settlement -> ledger has it, settlement doesn't ----
for idx in take(5):
    txn_id = transactions[idx]["txn_id"]
    del by_txn[txn_id]  # drop its settlement row
    record(
        txn_id,
        "missing_in_settlement",
        "Captured transaction has no matching settlement. Flag as pending "
        "settlement; escalate if unsettled beyond 2 business days.",
        "05_unsettled_transactions.md",
    )

# --- Type 2: duplicate_settlement -> two settlement rows for one txn -------
for idx in take(4):
    txn_id = transactions[idx]["txn_id"]
    orig = by_txn[txn_id]
    dup = dict(orig)
    dup["settlement_id"] = orig["settlement_id"].replace("STL", "DUP")
    settlements.append(dup)  # add the extra row directly
    record(
        txn_id,
        "duplicate_settlement",
        "Two settlements exist for one transaction. Retain the earliest "
        "settlement, reverse the duplicate, and adjust the ledger.",
        "06_duplicate_settlements.md",
    )

# --- Type 3: amount_mismatch -> settled off by MORE than tolerance/fees ----
for idx in take(5):
    txn_id = transactions[idx]["txn_id"]
    stl = by_txn[txn_id]
    bad = round(float(stl["settled_amount"]) * random.uniform(0.85, 0.95), 2)
    stl["settled_amount"] = money(bad)  # 5-15% short: not a fee, not rounding
    record(
        txn_id,
        "amount_mismatch",
        "Settled amount differs from (amount - fee) by more than the "
        "tolerance and is not explained by fees or FX. Flag for manual review.",
        "02_amount_tolerances.md",
    )

# --- Type 4: timing_difference -> settled beyond T+2 -----------------------
for idx in take(4):
    txn_id = transactions[idx]["txn_id"]
    stl = by_txn[txn_id]
    ts = datetime.fromisoformat(transactions[idx]["timestamp"])
    stl["settled_at"] = (ts + timedelta(days=random.randint(3, 6))).isoformat()
    record(
        txn_id,
        "timing_difference",
        "Settlement occurred beyond the acceptable T+2 window. Flag and record "
        "the delay reason; settlement within T+2 needs no action.",
        "07_settlement_timing.md",
    )

# --- Type 5: status_mismatch -> settlement refunded vs ledger captured -----
for idx in take(4):
    txn_id = transactions[idx]["txn_id"]
    stl = by_txn[txn_id]
    stl["status"] = "refunded"
    record(
        txn_id,
        "status_mismatch",
        "Settlement is 'refunded' while the ledger shows 'captured'. Requires a "
        "linked refund record; if none exists, escalate.",
        "08_status_reconciliation.md",
    )

# --- Distractors: within-tolerance noise that must NOT be flagged ----------
# These stay OUT of ground_truth on purpose -> they test for false positives.
for idx in take(6):
    txn_id = transactions[idx]["txn_id"]
    stl = by_txn[txn_id]
    noise = random.uniform(-0.90, 0.90)  # < TOLERANCE of 1.00 -> still a match
    stl["settled_amount"] = money(round(float(stl["settled_amount"]) + noise, 2))


# --------------------------------------------------------------------------
# 3. Shuffle row order (discrepancies shouldn't sit in predictable places)
#    and write everything out.
# --------------------------------------------------------------------------
final_settlements = list(by_txn.values()) + [
    s for s in settlements if s["settlement_id"].startswith("DUP")
]
random.shuffle(transactions)
random.shuffle(final_settlements)

TXN_FIELDS = ["txn_id", "timestamp", "amount", "currency", "merchant", "status"]
STL_FIELDS = ["settlement_id", "txn_ref", "settled_amount", "settled_at", "fee", "status"]

with open(DATA_DIR / "transactions.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=TXN_FIELDS)
    w.writeheader()
    w.writerows(transactions)

with open(DATA_DIR / "settlement.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=STL_FIELDS)
    w.writeheader()
    w.writerows(final_settlements)

with open(DATA_DIR / "ground_truth.json", "w") as f:
    json.dump(ground_truth, f, indent=2)


# --------------------------------------------------------------------------
# 4. Print a summary so you can sanity-check at a glance
# --------------------------------------------------------------------------
counts = {}
for g in ground_truth:
    counts[g["discrepancy_type"]] = counts.get(g["discrepancy_type"], 0) + 1

print("Wrote files to:", DATA_DIR.resolve())
print(f"  transactions.csv : {len(transactions)} rows")
print(f"  settlement.csv   : {len(final_settlements)} rows")
print(f"  ground_truth.json: {len(ground_truth)} injected discrepancies")
print("\nDiscrepancies by type:")
for k in sorted(counts):
    print(f"  {k:24s} {counts[k]}")
print("\n(+6 within-tolerance noise rows that must NOT be flagged.)")

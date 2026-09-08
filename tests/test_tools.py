"""
Unit tests for tools.py -- stdlib only, no pytest needed.

    python3 -m unittest discover tests -v

Two layers:
  * unit tests   -- hand-built rows, one discrepancy type each
  * eval test    -- full reconcile() against data/ + ground_truth.json
"""

import csv
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import detect_discrepancies, match_transactions, reconcile  # noqa: E402

DATA = Path(__file__).parent.parent / "data"


def txn(txn_id="TXN00001", amount="1000.00", timestamp="2025-01-01T10:00:00", status="captured"):
    return {"txn_id": txn_id, "timestamp": timestamp, "amount": amount,
            "currency": "INR", "merchant": "Amazon", "status": status}


def stl(txn_ref="TXN00001", settled_amount="980.00", fee="20.00",
        settled_at="2025-01-01T18:00:00", status="settled", settlement_id="STL00001"):
    return {"settlement_id": settlement_id, "txn_ref": txn_ref,
            "settled_amount": settled_amount, "settled_at": settled_at,
            "fee": fee, "status": status}


def types(found):
    return {d["txn_id"]: d["discrepancy_type"] for d in found}


class TestMatchTransactions(unittest.TestCase):
    def test_pairs_by_txn_ref(self):
        cases = match_transactions([txn()], [stl()])
        self.assertEqual(len(cases), 1)
        self.assertIsNotNone(cases[0]["ledger"])
        self.assertEqual(len(cases[0]["settlements"]), 1)

    def test_orphan_settlement_creates_case_with_no_ledger(self):
        cases = match_transactions([], [stl(txn_ref="TXN09999")])
        self.assertIsNone(cases[0]["ledger"])

    def test_ledger_with_no_settlement(self):
        cases = match_transactions([txn()], [])
        self.assertEqual(cases[0]["settlements"], [])

    def test_multiple_settlements_collected(self):
        cases = match_transactions([txn()], [stl(), stl(settlement_id="DUP00001")])
        self.assertEqual(len(cases[0]["settlements"]), 2)

    def test_is_pure_does_not_mutate_inputs(self):
        t, s = [txn()], [stl()]
        snapshot = (json.dumps(t, sort_keys=True), json.dumps(s, sort_keys=True))
        match_transactions(t, s)
        self.assertEqual(snapshot, (json.dumps(t, sort_keys=True), json.dumps(s, sort_keys=True)))


class TestDetectDiscrepancies(unittest.TestCase):
    def test_clean_match_is_not_reported(self):
        self.assertEqual(reconcile([txn()], [stl()]), [])

    def test_missing_in_settlement(self):
        found = reconcile([txn()], [])
        self.assertEqual(types(found), {"TXN00001": "missing_in_settlement"})

    def test_orphan_settlement(self):
        found = reconcile([], [stl(txn_ref="TXN09999")])
        self.assertEqual(types(found), {"TXN09999": "orphan_settlement"})

    def test_duplicate_settlement(self):
        found = reconcile([txn()], [stl(), stl(settlement_id="DUP00001")])
        self.assertEqual(types(found), {"TXN00001": "duplicate_settlement"})
        self.assertEqual(found[0]["evidence"]["settlement_count"], 2)

    def test_status_mismatch(self):
        found = reconcile([txn()], [stl(status="refunded")])
        self.assertEqual(types(found), {"TXN00001": "status_mismatch"})

    def test_amount_mismatch(self):
        # gross reconstructs to 900 vs ledger 1000 -> diff 100
        found = reconcile([txn()], [stl(settled_amount="880.00", fee="20.00")])
        self.assertEqual(types(found), {"TXN00001": "amount_mismatch"})
        self.assertEqual(found[0]["evidence"]["diff"], "100.00")

    def test_within_tolerance_noise_is_not_flagged(self):
        # 0.90 off, tolerance is 1.00 -> must stay silent (false-positive guard)
        self.assertEqual(reconcile([txn()], [stl(settled_amount="979.10")]), [])

    def test_tolerance_boundary_is_exclusive(self):
        # exactly 1.00 off -> not flagged (condition is abs(diff) > tolerance)
        self.assertEqual(reconcile([txn()], [stl(settled_amount="979.00")]), [])

    def test_timing_difference(self):
        found = reconcile([txn()], [stl(settled_at="2025-01-05T10:00:00")])
        self.assertEqual(types(found), {"TXN00001": "timing_difference"})
        self.assertEqual(found[0]["evidence"]["days_late"], 4)

    def test_t_plus_2_boundary_is_clean(self):
        self.assertEqual(reconcile([txn()], [stl(settled_at="2025-01-03T23:00:00")]), [])

    def test_duplicate_wins_over_amount_mismatch(self):
        """Precedence: a case with two issues reports the structural one."""
        found = reconcile([txn()], [stl(settled_amount="100.00"),
                                    stl(settlement_id="DUP00001", settled_amount="100.00")])
        self.assertEqual(types(found), {"TXN00001": "duplicate_settlement"})

    def test_status_wins_over_timing(self):
        found = reconcile([txn()], [stl(status="refunded", settled_at="2025-01-09T10:00:00")])
        self.assertEqual(types(found), {"TXN00001": "status_mismatch"})

    def test_custom_thresholds_are_honoured(self):
        cases = match_transactions([txn()], [stl(settled_amount="880.00")])
        self.assertEqual(detect_discrepancies(cases, tolerance=500.0), [])

    def test_empty_input(self):
        self.assertEqual(reconcile([], []), [])


class TestAgainstGroundTruth(unittest.TestCase):
    """The eval that matters: perfect precision/recall on the generated dataset."""

    @classmethod
    def setUpClass(cls):
        with open(DATA / "transactions.csv") as f:
            cls.txns = list(csv.DictReader(f))
        with open(DATA / "settlement.csv") as f:
            cls.stls = list(csv.DictReader(f))
        with open(DATA / "ground_truth.json") as f:
            cls.truth = {g["txn_id"]: g["discrepancy_type"] for g in json.load(f)}
        cls.found = types(reconcile(cls.txns, cls.stls))

    def test_no_missed_discrepancies(self):
        self.assertEqual(set(self.truth) - set(self.found), set(), "recall < 1.0")

    def test_no_false_positives(self):
        self.assertEqual(set(self.found) - set(self.truth), set(), "precision < 1.0")

    def test_every_type_classified_correctly(self):
        wrong = {i: (self.truth[i], self.found[i])
                 for i in set(self.truth) & set(self.found) if self.truth[i] != self.found[i]}
        self.assertEqual(wrong, {}, f"misclassified: {wrong}")


if __name__ == "__main__":
    unittest.main()

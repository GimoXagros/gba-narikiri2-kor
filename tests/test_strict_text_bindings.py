"""Source-bound oracle tests against the exact local JP and adopted KO ROMs."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from strict_text_bindings import (  # noqa: E402
    BASELINE_SHA256, JP_SHA256, ROM_SIZE, build_bindings, load_csv,
    require_image, summary,
)


class StrictTextBindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jp = (ROOT / "Japanese.gba").read_bytes()
        cls.ko = (ROOT / "private_validation/listperf-20261002/root/credits-build-a/"
                  "Xagros_Narikiri2_KOR_v1.0_listperf-pass01_credits_TEST.gba").read_bytes()
        cls.catalog = load_csv(ROOT / "private_validation/listperf-20261002/luna-audit/TEXT_SLOT_MAP.csv")
        cls.audit = load_csv(ROOT / "analysis/v0.9c/pointer_audit.csv")

    def test_full_oracle_and_seven_conflicts(self):
        require_image(self.jp, JP_SHA256, ROM_SIZE, "Japanese")
        require_image(self.ko, BASELINE_SHA256, 13270790, "baseline")
        rows = build_bindings(self.jp, self.ko, self.catalog, self.audit)
        self.assertEqual(len(rows), 10172)
        self.assertEqual(len({r["jp_text_start"] for r in rows}), 9246)
        self.assertEqual(len(summary(rows)["semantic_conflict_details"]), 7)
        self.assertEqual(sum(r["fit_status"] == "ALIAS_SEMANTIC_CONFLICT" for r in rows), 14)
        self.assertTrue(all(r["proven_slot_end"] <= r["jp_raw_end"] + 1 for r in rows))
        self.assertTrue(all(r["slot_capacity"] <= r["jp_raw_end"] + 1 - r["jp_text_start"] for r in rows))

    def test_catalog_pointer_disagreement_is_rejected(self):
        rows = [dict(r) for r in self.catalog]
        rows[0]["jp_pointer_value"] = "08000000"
        with self.assertRaisesRegex(ValueError, "catalog jp_pointer_value differs"):
            build_bindings(self.jp, self.ko, rows, self.audit)

    def test_old_audit_identity_disagreement_is_rejected(self):
        audit = [dict(r) for r in self.audit]
        target = next(r for r in audit if r["kind"] == "full_text")
        target["id"] = "WRONG_ID"
        with self.assertRaisesRegex(ValueError, "audit identity/type disagreement"):
            build_bindings(self.jp, self.ko, self.catalog, audit)

    def test_baseline_payload_disagreement_is_rejected(self):
        ko = bytearray(self.ko)
        start = int(self.catalog[0]["latest_text_start_offset"], 16)
        ko[start] ^= 1
        with self.assertRaisesRegex(ValueError, "KO body hash differs"):
            build_bindings(self.jp, ko, self.catalog, self.audit)


if __name__ == "__main__":
    unittest.main()

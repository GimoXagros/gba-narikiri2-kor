"""Real-source guards for the original-slot tone retest builder."""

from __future__ import annotations

import copy
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_dialogue_tone_inplace import build_inplace, slot_refs  # noqa: E402
from build_dialogue_tone import sha  # noqa: E402


class InplaceToneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = ROOT / "private_validation/release-v1.0/Xagros_Narikiri2_KOR_v1.0.gba"
        jp = ROOT / "Japanese.gba"
        if not base.exists() or not jp.exists():
            raise unittest.SkipTest("Private source ROM fixtures unavailable")
        cls.base, cls.jp = base.read_bytes(), jp.read_bytes()
        cls.decisions = json.loads((ROOT / "translation/dialogue_tone_pass01.json").read_text("utf-8"))

    def test_exact_sourcebound_inplace_build(self):
        result, report = build_inplace(self.base, self.jp, self.decisions)
        self.assertEqual(sha(result), "8d4c8dca40d7fdaa561dfa64fecc6ef42c04a11cdd345553e7bc5bb30313c142")
        self.assertEqual(len(result), len(self.base))
        self.assertEqual(report["status"], "LOCAL_RETEST_CANDIDATE_VBA_UNVERIFIED")
        self.assertEqual([w["padding_bytes"] for w in report["writes"]], [0, 4, 0])
        for row in report["writes"]:
            storage = int(row["storage"], 16)
            self.assertEqual(result[storage:storage + 4], self.base[storage:storage + 4])

    def test_wrong_base_and_reapply_rejected(self):
        result, _ = build_inplace(self.base, self.jp, self.decisions)
        with self.assertRaisesRegex(ValueError, "identity"):
            build_inplace(result, self.jp, self.decisions)
        damaged = bytearray(self.base)
        damaged[0] ^= 1
        with self.assertRaisesRegex(ValueError, "identity"):
            build_inplace(bytes(damaged), self.jp, self.decisions)

    def test_overlength_edit_rejected_by_original_slot_guard(self):
        decisions = copy.deepcopy(self.decisions)
        decisions[1]["after"] = "그럼，천천히 쉬다 가세요오오．"
        with self.assertRaisesRegex(ValueError, "original slot"):
            build_inplace(self.base, self.jp, decisions)

    def test_interior_shared_pointer_detection(self):
        rom = bytearray(64)
        rom[0:4] = struct.pack("<I", 0x08000010)
        rom[8:12] = struct.pack("<I", 0x08000012)
        self.assertEqual(slot_refs(bytes(rom), 16, 20), [(16, 0), (18, 8)])


if __name__ == "__main__":
    unittest.main()

"""Real-source guards for the local three-binding voice candidate."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_dialogue_tone import ascii_marker_controls, build, require_identity, sha  # noqa: E402
from scan_dialogue_tone_candidates import scan  # noqa: E402


class ToneBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_path = ROOT / "private_validation/release-v1.0/Xagros_Narikiri2_KOR_v1.0.gba"
        cls.jp_path = ROOT / "Japanese.gba"
        if not cls.base_path.exists() or not cls.jp_path.exists():
            raise unittest.SkipTest("Private licensed source ROM fixtures unavailable")
        cls.base = cls.base_path.read_bytes()
        cls.jp = cls.jp_path.read_bytes()
        cls.decisions = json.loads((ROOT / "translation/dialogue_tone_pass01.json").read_text("utf-8"))

    def test_exact_rebuild_and_reapply_rejection(self):
        result, report = build(self.base, self.jp, self.decisions)
        self.assertEqual(sha(result), "4243f300f579277ff63dc6fe15a6043419b0f9684d11f9354972acf6c3bcb080")
        self.assertEqual(report["changed_bindings"], 3)
        with self.assertRaisesRegex(ValueError, "identity"):
            require_identity(result, self.jp)

    def test_wrong_source_and_before_hash_rejected(self):
        damaged = bytearray(self.base)
        damaged[0] ^= 1
        with self.assertRaisesRegex(ValueError, "identity"):
            build(bytes(damaged), self.jp, self.decisions)
        changed = copy.deepcopy(self.decisions)
        changed[0]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            build(self.base, self.jp, changed)
        changed = copy.deepcopy(self.decisions)
        changed[0]["before_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            build(self.base, self.jp, changed)

    def test_controls_and_numbers_rejected(self):
        changed = copy.deepcopy(self.decisions)
        changed[0]["after"] = changed[0]["after"].replace("@L", "")
        with self.assertRaisesRegex(ValueError, "control"):
            build(self.base, self.jp, changed)
        changed = copy.deepcopy(self.decisions)
        changed[1]["after"] += "2"
        with self.assertRaisesRegex(ValueError, "Numeric"):
            build(self.base, self.jp, changed)

    def test_duplicate_and_unreviewed_binding_rejected(self):
        with self.assertRaisesRegex(ValueError, "three reviewed"):
            build(self.base, self.jp, self.decisions + [copy.deepcopy(self.decisions[0])])
        changed = copy.deepcopy(self.decisions)
        changed[0]["binding"] = "D02517:00349614"  # shared greeting in the same event
        with self.assertRaisesRegex(ValueError, "three reviewed"):
            build(self.base, self.jp, changed)

    def test_literal_marker_skips_two_byte_glyph_trail(self):
        self.assertEqual(ascii_marker_controls(bytes.fromhex("8a40404c")), (b"@L",))
        with self.assertRaisesRegex(ValueError, "Unrecognized"):
            ascii_marker_controls(b"@?")

    def test_six_normal_or_unknown_cases_are_advisory_only(self):
        # Synthetic fixtures; they demonstrate policy and are not game dialogue.
        cases = [
            ("speaker_a", "안녕하세요．"),        # a speaker switch may change register
            ("speaker_b", "어서 와．"),
            ("quoted_casual", "그는 『괜찮아』라고 했어요．"),
            ("monologue", "괜찮을까？@P안녕하세요．"),
            ("natural_endings", "먼저 가요．다녀오세요．"),
            ("shared_a", "어서 오세요．"),
            ("shared_b", "어서 오세요．"),   # same string can have multiple use-sites
            ("unknown", "정말이야？ 고맙습니다．"),
        ]
        full = [[key, key.split("_")[0], None, None, "", value] for key, value in cases]
        book = {"full": full, "compact": []}
        frozen = copy.deepcopy(book)
        report = scan(book, {"records": {}})
        self.assertEqual(book, frozen)  # scanner never changes prose
        self.assertEqual(report["full_text_bindings_scanned"], len(cases))
        self.assertEqual([x["binding_id"] for x in report["candidates"]], ["unknown"])
        self.assertEqual(report["candidates"][0]["review_status"], "NEEDS_SCENE_CONTEXT")


if __name__ == "__main__":
    unittest.main()

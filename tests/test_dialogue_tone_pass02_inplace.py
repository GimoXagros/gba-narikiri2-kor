"""Source-bound regression guards for the full first-pass voice candidate."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_dialogue_tone_pass02_inplace import build, sha  # noqa: E402
from confirmed_text_edits import encode_full  # noqa: E402


class FullToneInplaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sources = {
            "base": ROOT / "private_validation/tone-freeze-debug/build-inplace-a/Xagros_Narikiri2_KOR_v1.0_tone-pass01-inplace-retest.gba",
            "jp": ROOT / "Japanese.gba",
            "catalog": ROOT / "analysis/v0.9c/pointer_audit.csv",
            "book": ROOT / "private_validation/tone-freeze-debug/build-inplace-a/final-dialogue-book.json",
        }
        if any(not path.exists() for path in sources.values()):
            raise unittest.SkipTest("Private licensed source ROM/corpus fixtures unavailable")
        cls.base = sources["base"].read_bytes()
        cls.jp = sources["jp"].read_bytes()
        cls.catalog = sources["catalog"].read_bytes()
        cls.book = sources["book"].read_bytes()
        cls.decisions = json.loads((ROOT / "translation/dialogue_tone_pass02.json").read_text("utf-8"))

    def run_build(self, decisions=None, base=None):
        return build(self.base if base is None else base, self.jp,
                     self.decisions if decisions is None else decisions,
                     self.catalog, self.book)

    def test_exact_original_slot_candidate(self):
        candidate, corpus, report, mapping = self.run_build()
        self.assertEqual(sha(candidate), "26da89ccb5441af705e10c7660b533216ab39390bc4caa06827ccd12ce77fda1")
        self.assertEqual(len(candidate), len(self.base))
        self.assertEqual((report["writer_count"], report["affected_bindings"]), (70, 75))
        self.assertEqual(len(mapping["affected_bindings"]), 75)
        self.assertEqual(len(json.loads(corpus)["full"]), 8945)

    def test_wrong_base_and_source_hash_rejected(self):
        damaged = bytearray(self.base)
        damaged[-100] ^= 1
        with self.assertRaisesRegex(ValueError, "identity"):
            self.run_build(base=bytes(damaged))
        decisions = copy.deepcopy(self.decisions)
        decisions[0]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source text identity"):
            self.run_build(decisions)

    def test_frozen_corpus_content_rejected_even_with_same_meta(self):
        tampered = json.loads(self.book)
        tampered["full"][0][4] = "변조된 일본어 원문"
        raw = json.dumps(tampered, ensure_ascii=False).encode("utf-8")
        with self.assertRaisesRegex(ValueError, "baseline dialogue corpus identity"):
            build(self.base, self.jp, self.decisions, self.catalog, raw)

    def test_shared_alias_and_control_rejected(self):
        decisions = copy.deepcopy(self.decisions)
        row = next(r for r in decisions if r["binding"] == "D01065:00315690")
        row["affected_bindings"] = row["affected_bindings"][:1]
        with self.assertRaisesRegex(ValueError, "shared-slot consumer"):
            self.run_build(decisions)
        decisions = copy.deepcopy(self.decisions)
        row = next(r for r in decisions if r["binding"] == "D06466:00738390")
        row["after"] = row["after"].replace("@P", "", 1)
        row["new_payload_bytes"] = len(encode_full(row["after"]))
        with self.assertRaisesRegex(ValueError, "Raw marker"):
            self.run_build(decisions)

    def test_overlength_and_duplicate_writer_rejected(self):
        decisions = copy.deepcopy(self.decisions)
        decisions[0]["after"] += "가" * 100
        decisions[0]["new_payload_bytes"] = len(encode_full(decisions[0]["after"]))
        with self.assertRaisesRegex(ValueError, "slot byte capacity"):
            self.run_build(decisions)
        with self.assertRaisesRegex(ValueError, "duplicate writer"):
            self.run_build(self.decisions + [copy.deepcopy(self.decisions[0])])


if __name__ == "__main__":
    unittest.main()

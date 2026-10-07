"""Bounded diagnostic arena and exact notice replacement checks."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from strict_boot_notice_lz import assemble_diagnostic, plan_notice_lz
from strict_layout_core import Write
from build_banked_font import assemble

SOURCE = ROOT.parent / "narikiri2-v09d-graphics-test"
JP = SOURCE / "Japanese.gba"
KO = SOURCE / ("private_validation/listperf-20261002/root/credits-build-a/"
               "Xagros_Narikiri2_KOR_v1.0_listperf-pass01_credits_TEST.gba")


class SyntheticBootSource(unittest.TestCase):
    def test_thumb_wrapper_has_one_bios_lz_call_and_original_return(self):
        body = assemble(ROOT / "asm/strict_boot_notice_lz.s", 0xC90000, 0, 512)
        self.assertLessEqual(len(body), 140)
        self.assertEqual(body.count(b"\x12\xdf"), 1)
        self.assertIn(struct.pack("<I", 0x08C91000), body)
        self.assertEqual(body[-4:], struct.pack("<I", 0x08007401))


@unittest.skipUnless(JP.exists() and KO.exists(), "private source ROMs unavailable")
class BootNoticeLzPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jp, cls.ko = JP.read_bytes(), KO.read_bytes()

    def test_exact_replacement_and_arena(self):
        writes, report = plan_notice_lz(self.ko, self.jp)
        self.assertEqual(report["arena_start"], 0xC933C4)
        self.assertEqual(report["arena_end"], 0xCA3C00)
        self.assertEqual(report["arena_bytes"], 67644)
        self.assertEqual(len(writes), 2)
        self.assertEqual(sum(1 for hit in report["pointer_shaped_hits"]
                             if hit["classification"] == "matched_notice_wrapper_literal"), 1)
        output, assembled = assemble_diagnostic(self.ko, self.jp)
        self.assertEqual(len(output), len(self.ko))
        self.assertEqual(assembled["extra_writes"], 0)
        for write in writes:
            self.assertEqual(output[write.start:write.end], write.after)
        self.assertEqual(output[report["arena_start"]:report["arena_end"]],
                         self.ko[report["arena_start"]:report["arena_end"]])

    def test_arena_bounds_and_expected_source_enforced(self):
        _, report = plan_notice_lz(self.ko, self.jp)
        start = report["arena_start"]
        good = Write("test:book", start, self.ko[start:start+4], b"BOOK",
                     "diagnostic", "test consumer", "fixture", ("bound",))
        output, assembled = assemble_diagnostic(self.ko, self.jp, (good,))
        self.assertEqual(output[start:start+4], b"BOOK")
        self.assertEqual(assembled["extra_writes"], 1)
        outside = Write("test:outside", report["arena_end"]-2,
                        self.ko[report["arena_end"]-2:report["arena_end"]+2],
                        b"FAIL", "diagnostic", "test consumer", "fixture", ("bound",))
        with self.assertRaisesRegex(ValueError, "exceeds reclaimed notice owner"):
            assemble_diagnostic(self.ko, self.jp, (outside,))
        stale = Write("test:stale", start, b"bad!", b"BOOK",
                      "diagnostic", "test consumer", "fixture", ("bound",))
        with self.assertRaisesRegex(ValueError, "expected-source"):
            assemble_diagnostic(self.ko, self.jp, (stale,))


if __name__ == "__main__":
    unittest.main()

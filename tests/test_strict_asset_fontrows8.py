"""Eight-glyph direct-row variant round trip and exact tight owner."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from strict_asset_fontrows8 import (
    FONT_START, FONT_END, ARENA_START, PACKED_END,
    pack_font_rows8, unpack_font_rows8, plan_font_rows8, assemble_diagnostic8,
)

SOURCE = ROOT.parent / "narikiri2-v09d-graphics-test"
JP = SOURCE / "Japanese.gba"
KO = SOURCE / ("private_validation/listperf-20261002/root/credits-build-a/"
               "Xagros_Narikiri2_KOR_v1.0_listperf-pass01_credits_TEST.gba")


class SyntheticBlockFont(unittest.TestCase):
    def test_all_glyphs_round_trip_and_short_block_rejection(self):
        glyphs = []
        for index in range(3840):
            rows = [0] * 16
            rows[0] = index % 300 + 1
            rows[1] = index * 7 % 300 + 1
            glyphs.append(struct.pack("<16H", *rows))
        raw = b"".join(glyphs)
        blob, report = pack_font_rows8(raw)
        self.assertEqual(unpack_font_rows8(blob, report["mask_values"],
                                           report["dictionary_rows"]), raw)
        self.assertEqual(report["block_glyphs"], 8)
        self.assertEqual(report["group_base_bytes"], 960)
        with self.assertRaisesRegex(ValueError, "truncated"):
            unpack_font_rows8(blob[:4], report["mask_values"],
                              report["dictionary_rows"])


@unittest.skipUnless(JP.exists() and KO.exists(), "private source ROMs unavailable")
class ExactBlockFont(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jp, cls.ko = JP.read_bytes(), KO.read_bytes()

    def test_tight_layout_and_diagnostic_image(self):
        writes, report = plan_font_rows8(self.jp, self.ko)
        self.assertEqual(report["codec"]["packed_bytes"], 53382)
        self.assertEqual(report["row_sections"]["ids"][0], FONT_START)
        self.assertEqual(report["row_sections"]["symbols"][1], PACKED_END)
        self.assertEqual(report["decoder"], [0xB9490, 0xB9510])
        self.assertEqual(report["wrapper14"], [0xB9520, 0xB9554])
        self.assertEqual(report["wrapper21"], [0xB9560, 0xB95AC])
        self.assertEqual(report["lookup"], [0xB95B0, 0xB95B4])
        self.assertEqual(report["product_arena"], [ARENA_START, FONT_END])
        self.assertEqual(report["product_arena_bytes"], 69172)
        self.assertEqual(len(writes), 9)
        image, assembled = assemble_diagnostic8(self.jp, self.ko)
        self.assertEqual(len(image), len(self.ko))
        self.assertEqual(assembled["product_arena_bytes"], 69172)
        self.assertEqual(image[ARENA_START:FONT_END], self.ko[ARENA_START:FONT_END])
        for row in writes:
            self.assertEqual(image[row.start:row.end], row.after)


if __name__ == "__main__":
    unittest.main()

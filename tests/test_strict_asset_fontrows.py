"""Direct-row native full-font codec and exact-source relocation tests."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from strict_asset_fontrows import (
    ARENA_START, DECODER, FONT_END, FONT_START, GLYPHS, LOOKUP_221E,
    NEAR_VENEER, PACKED_END, WRAPPER_14E0, WRAPPER_21F4,
    assemble_diagnostic, pack_font_rows, plan_font_rows, unpack_font_rows,
)

SOURCE = ROOT.parent / "narikiri2-v09d-graphics-test"
JP = SOURCE / "Japanese.gba"
KO = SOURCE / ("private_validation/listperf-20261002/root/credits-build-a/"
               "Xagros_Narikiri2_KOR_v1.0_listperf-pass01_credits_TEST.gba")


class SyntheticRowCodec(unittest.TestCase):
    def test_full_glyph_count_round_trip_and_determinism(self):
        glyphs = []
        for glyph in range(GLYPHS):
            rows = [0] * 16
            rows[0] = glyph % 300 + 1
            rows[1] = glyph * 7 % 300 + 1
            rows[12] = 0x7FFF if glyph % 17 == 0 else 0
            glyphs.append(struct.pack("<16H", *rows))
        raw = b"".join(glyphs)
        encoded, report = pack_font_rows(raw)
        self.assertEqual(report["glyphs"], GLYPHS)
        self.assertEqual(report["dictionary_rows"], 255)
        self.assertEqual(unpack_font_rows(encoded, report["mask_values"],
                                          report["dictionary_rows"]), raw)
        self.assertEqual(pack_font_rows(raw), (encoded, report))
        with self.assertRaisesRegex(ValueError, "3,840"):
            pack_font_rows(raw[:-1])

    def test_invalid_table_and_mask_index_fail_closed(self):
        raw = struct.pack("<16H", *([1] + [0] * 15)) * GLYPHS
        encoded, report = pack_font_rows(raw)
        with self.assertRaisesRegex(ValueError, "table size"):
            unpack_font_rows(encoded, 257, report["dictionary_rows"])
        broken = bytearray(encoded)
        broken[0] = 255
        with self.assertRaisesRegex(ValueError, "mask index"):
            unpack_font_rows(bytes(broken), report["mask_values"],
                             report["dictionary_rows"])


@unittest.skipUnless(JP.exists() and KO.exists(), "private source ROMs unavailable")
class ExactSourceFontRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jp, cls.ko = JP.read_bytes(), KO.read_bytes()

    def test_all_glyphs_and_tight_owner_nodes(self):
        writes, report = plan_font_rows(self.jp, self.ko)
        self.assertEqual(report["codec"]["packed_bytes"], 56262)
        self.assertEqual(report["codec"]["dictionary_rows"], 255)
        self.assertEqual(report["codec"]["escaped_rows"], 3194)
        self.assertEqual(report["byte_identical_jp_glyphs"], 1266)
        self.assertEqual(report["row_sections"]["ids"], [FONT_START, 0xAD2F4])
        self.assertEqual(report["row_sections"]["symbols"], [0xB9DBC, PACKED_END])
        self.assertEqual(report["decoder"], [DECODER, DECODER + 100])
        self.assertEqual(report["wrapper14"], [WRAPPER_14E0, WRAPPER_14E0 + 52])
        self.assertEqual(report["wrapper21"], [WRAPPER_21F4, WRAPPER_21F4 + 76])
        self.assertEqual(report["lookup"], [LOOKUP_221E, LOOKUP_221E + 4])
        self.assertEqual(report["near_veneer"], [NEAR_VENEER, NEAR_VENEER + 8])
        self.assertEqual(report["product_arena"], [ARENA_START, FONT_END])
        self.assertEqual(report["product_arena_bytes"], 66340)
        self.assertEqual(len(writes), 9)
        image, assembled = assemble_diagnostic(self.jp, self.ko)
        self.assertEqual(len(image), len(self.ko))
        self.assertEqual(assembled["product_arena_bytes"], 66340)
        for row in writes:
            self.assertEqual(image[row.start:row.end], row.after)
        self.assertEqual(image[ARENA_START:FONT_END], self.ko[ARENA_START:FONT_END])

    def test_source_identity_and_reference_population(self):
        with self.assertRaisesRegex(ValueError, "Japanese 8 MiB"):
            plan_font_rows(self.jp[:-1], self.ko)
        with self.assertRaisesRegex(ValueError, "Adopted Korean"):
            plan_font_rows(self.jp, self.ko[:-1])


if __name__ == "__main__":
    unittest.main()

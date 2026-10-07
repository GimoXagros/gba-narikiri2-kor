"""Lossless 1bpp boot bitmap and bounded diagnostic relocation checks."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_banked_font import assemble
from strict_boot_notice_1bpp import (
    RAW_BYTES, PLANE_BYTES, SCRATCH_START, SCRATCH_END, VISIBLE_END,
    WRAPPER_START, WRAPPER_END, PIXELS_START, PIXELS_END, VRAM_END,
    assemble_diagnostic, expand_1bpp, make_lut, pack_1bpp, plan_notice_1bpp,
)
from strict_layout_core import Write

SOURCE = ROOT.parent / "narikiri2-v09d-graphics-test"
JP = SOURCE / "Japanese.gba"
KO = SOURCE / ("private_validation/listperf-20261002/root/credits-build-a/"
               "Xagros_Narikiri2_KOR_v1.0_listperf-pass01_credits_TEST.gba")


class SyntheticBootNotice1bpp(unittest.TestCase):
    def test_every_lut_entry_has_exact_four_rgb555_pixels(self):
        lut = make_lut()
        self.assertEqual(len(lut), 128)
        for nibble in range(16):
            actual = struct.unpack_from("<4H", lut, nibble * 8)
            expected = tuple(0x7FFF if nibble & (8 >> bit) else 0
                             for bit in range(4))
            self.assertEqual(actual, expected)

    def test_bitplane_exact_geometry_and_palette(self):
        plane = bytes((i * 73 + i // 9) & 255 for i in range(PLANE_BYTES))
        raw = expand_1bpp(plane)
        self.assertEqual(len(raw), RAW_BYTES)
        self.assertEqual(pack_1bpp(raw), plane)
        with self.assertRaisesRegex(ValueError, "geometry"):
            pack_1bpp(raw[:-2])
        with self.assertRaisesRegex(ValueError, "color"):
            pack_1bpp(b"\x01\x00" + raw[2:])
        with self.assertRaisesRegex(ValueError, "geometry"):
            expand_1bpp(plane[:-1])

    def test_assembled_thumb1_wrapper_and_offscreen_scratch_bounds(self):
        body = assemble(ROOT / "asm/strict_boot_notice_1bpp.s",
                        WRAPPER_START, 0, WRAPPER_END - WRAPPER_START)
        self.assertEqual(len(body), 340)
        self.assertEqual(body.count(b"\x12\xdf"), 1)
        self.assertIn(struct.pack("<I", 0x08000000 + PIXELS_START), body)
        self.assertIn(struct.pack("<I", SCRATCH_START), body)
        self.assertIn(struct.pack("<I", 0x08007401), body)
        self.assertEqual(body[-128:], make_lut())
        self.assertLessEqual(WRAPPER_START + len(body), WRAPPER_END)
        self.assertLessEqual(VISIBLE_END, SCRATCH_START)
        self.assertLessEqual(SCRATCH_END, VRAM_END)


@unittest.skipUnless(JP.exists() and KO.exists(), "private source ROMs unavailable")
class ExactSourceBootNotice1bpp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jp, cls.ko = JP.read_bytes(), KO.read_bytes()

    def test_lossless_replacement_and_conditional_arena(self):
        writes, report = plan_notice_1bpp(self.ko, self.jp)
        self.assertEqual(len(writes), 2)
        self.assertEqual(report["colors"], {"0000": 36507, "7FFF": 1893})
        self.assertEqual(report["bitplane_bytes"], 4800)
        self.assertEqual(report["lz_bytes"], 1260)
        self.assertEqual(report["arena_start"], 0xC914EC)
        self.assertEqual(report["arena_end"], PIXELS_END)
        self.assertEqual(report["arena_bytes"], 75540)
        self.assertEqual(sum(hit["classification"] == "matched_notice_wrapper_literal"
                             for hit in report["pointer_shaped_hits"]), 1)
        output, assembled = assemble_diagnostic(self.ko, self.jp)
        self.assertEqual(len(output), len(self.ko))
        self.assertEqual(assembled["extra_writes"], 0)
        for row in writes:
            self.assertEqual(output[row.start:row.end], row.after)
        self.assertEqual(output[report["arena_start"]:PIXELS_END],
                         self.ko[report["arena_start"]:PIXELS_END])

    def test_source_hash_and_write_owner_rejection(self):
        with self.assertRaisesRegex(ValueError, "Exact adopted"):
            plan_notice_1bpp(self.ko[:-1], self.jp)
        with self.assertRaisesRegex(ValueError, "Exact 8 MiB"):
            plan_notice_1bpp(self.ko, self.jp[:-1])
        _, report = plan_notice_1bpp(self.ko, self.jp)
        start = report["arena_start"]
        good = Write("test:book", start, self.ko[start:start + 4], b"BOOK",
                     "diagnostic", "test consumer", "fixture", ("bound",))
        output, assembled = assemble_diagnostic(self.ko, self.jp, (good,))
        self.assertEqual(output[start:start + 4], b"BOOK")
        self.assertEqual(assembled["extra_writes"], 1)
        outside = Write("test:outside", PIXELS_END - 2,
                        self.ko[PIXELS_END - 2:PIXELS_END + 2], b"FAIL",
                        "diagnostic", "test consumer", "fixture", ("bound",))
        with self.assertRaisesRegex(ValueError, "exceeds reclaimed notice owner"):
            assemble_diagnostic(self.ko, self.jp, (outside,))
        stale = Write("test:stale", start, b"bad!", b"BOOK",
                      "diagnostic", "test consumer", "fixture", ("bound",))
        with self.assertRaisesRegex(ValueError, "expected-source"):
            assemble_diagnostic(self.ko, self.jp, (stale,))


if __name__ == "__main__":
    unittest.main()

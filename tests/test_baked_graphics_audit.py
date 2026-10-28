"""Guard visual audit layer order and the approved font exclusion boundary."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_baked_graphics import diagnose_legacy_rl, font_source, render


class BakedGraphicsAuditTests(unittest.TestCase):
    def test_gold_face_over_emblem_and_ribbon_over_face(self):
        rom = bytearray(0x376A0C)
        raw = bytes([0x11] * 32 + [0x22] * 32 + [0x33] * 32)
        for bank, index, color in ((1, 1, 31), (2, 2, 31 << 5), (0, 3, 31 << 10)):
            struct.pack_into('<H', rom, 0x37694C + bank * 32 + index * 2, color)
        sprites = [(4, 0, 8, 8, 2, 0), (2, 0, 8, 8, 1, 2), (0, 0, 8, 8, 0, 1)]
        picture = render(raw, rom, sprites)
        self.assertEqual(picture.getpixel((0, 0)), (255, 0, 0))
        self.assertEqual(picture.getpixel((2, 0)), (0, 255, 0))
        self.assertEqual(picture.getpixel((4, 0)), (0, 0, 255))

    def test_approved_font_assets_excluded_and_bespoke_assets_eligible(self):
        self.assertTrue(font_source(0x3768F8, 12))
        self.assertTrue(font_source(0x380F08, 9))
        self.assertTrue(font_source(0x3A7ADC, 74))
        self.assertFalse(font_source(0x3768F8, 9))
        self.assertFalse(font_source(0x3A7ADC, 1))

    def test_overlong_legacy_packet_is_diagnosed_and_never_accepted(self):
        result = diagnose_legacy_rl(bytes.fromhex('3008000089ff'), 0)
        self.assertEqual(result['output_overshoot'], 4)
        self.assertEqual(result['consumed_bytes'], 6)
        self.assertFalse(result['accepted_asset'])
        with self.assertRaises(ValueError):
            diagnose_legacy_rl(bytes.fromhex('3008000089'), 0)


if __name__ == '__main__':
    unittest.main()

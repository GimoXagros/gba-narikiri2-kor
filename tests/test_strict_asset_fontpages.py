"""Public, synthetic checks for the fixed full-font page representation."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from find_gba_lz77_asset import decompress_lz77_stream
from strict_asset_fontpages import (
    FONT_START, GLYPH_COUNT, GLYPH_SIZE, LOOKUP_221E,
    PAGE_BYTES, PAGE_COUNT, WRAPPER_14E0, WRAPPER_21F4,
    WRAPPER_14E0_32, WRAPPER_21F4_32, LOOKUP_221E_32,
    WRAPPER_14E0_SOURCE, WRAPPER_21F4_SOURCE, LOOKUP_221E_SOURCE,
    WRAPPER_14E0_32_SOURCE, WRAPPER_21F4_32_SOURCE, LOOKUP_221E_32_SOURCE,
    _assemble, _entry_jump, _near_jump, pack_pages,
)


class FontPageCodecTests(unittest.TestCase):
    def test_every_synthetic_glyph_round_trips(self):
        original = b"".join(bytes((index & 0xFF,)) * GLYPH_SIZE
                            for index in range(GLYPH_COUNT))
        packed, budget = pack_pages(original)
        self.assertEqual(budget["source_sha256"], __import__("hashlib").sha256(original).hexdigest())
        self.assertEqual(budget["page_count"], PAGE_COUNT)
        self.assertLess(budget["packed_end"], WRAPPER_14E0)
        self.assertEqual(len(packed), budget["packed_bytes"])
        for page in range(PAGE_COUNT):
            pointer = struct.unpack_from("<I", packed, page * 4)[0]
            self.assertEqual(pointer & 3, 0)
            decoded, _ = decompress_lz77_stream(packed, pointer - 0x08000000 - FONT_START,
                                                  PAGE_BYTES)
            self.assertEqual(decoded, original[page * PAGE_BYTES:(page + 1) * PAGE_BYTES])

    def test_wrong_font_length_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "3,840"):
            pack_pages(bytes(GLYPH_COUNT * GLYPH_SIZE - 1))

    def test_32_glyph_page_profile_round_trips(self):
        original = b"".join(bytes((index & 0xFF,)) * GLYPH_SIZE
                            for index in range(GLYPH_COUNT))
        packed, budget = pack_pages(original, page_glyphs=32)
        self.assertEqual(budget["page_count"], 120)
        self.assertEqual(budget["page_bytes"], 1024)
        self.assertLess(budget["packed_end"], WRAPPER_14E0_32)
        for page in range(120):
            pointer = struct.unpack_from("<I", packed, page * 4)[0]
            decoded, _ = decompress_lz77_stream(packed, pointer - 0x08000000 - FONT_START,
                                                  1024)
            self.assertEqual(decoded, original[page * 1024:(page + 1) * 1024])

    def test_thumb_wrappers_fit_reserved_slots(self):
        first = _assemble(WRAPPER_14E0_SOURCE, WRAPPER_14E0, 0x100)
        second = _assemble(WRAPPER_21F4_SOURCE, WRAPPER_21F4, 0x100)
        lookup = _assemble(LOOKUP_221E_SOURCE, LOOKUP_221E, 0x40)
        self.assertIn(b"\x11\xdf", first)
        self.assertIn(b"\x11\xdf", second)
        self.assertLessEqual(WRAPPER_14E0 + len(first), WRAPPER_21F4)
        self.assertLessEqual(WRAPPER_21F4 + len(second), LOOKUP_221E)
        self.assertEqual(len(lookup), 12)
        self.assertEqual(_entry_jump(WRAPPER_14E0)[:4], b"\x00\x4b\x18\x47")
        self.assertEqual(_near_jump(LOOKUP_221E)[:4], b"\x00\x4a\x10\x47")
        first32 = _assemble(WRAPPER_14E0_32_SOURCE, WRAPPER_14E0_32, 0x100)
        second32 = _assemble(WRAPPER_21F4_32_SOURCE, WRAPPER_21F4_32, 0x100)
        lookup32 = _assemble(LOOKUP_221E_32_SOURCE, LOOKUP_221E_32, 0x40)
        self.assertIn(b"\x11\xdf", first32)
        self.assertIn(b"\x11\xdf", second32)
        self.assertLessEqual(WRAPPER_14E0_32 + len(first32), WRAPPER_21F4_32)
        self.assertLessEqual(WRAPPER_21F4_32 + len(second32), LOOKUP_221E_32)
        self.assertEqual(len(lookup32), 12)


if __name__ == "__main__":
    unittest.main()

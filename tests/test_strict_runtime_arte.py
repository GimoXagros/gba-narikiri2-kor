"""Synthetic shared-start ARTE context and selector checks."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from strict_runtime_arte import ARTE_TABLE_OFFSET, ARTE_STRIDE, decode_name
from strict_unit_codec import build_book, encode_parts, factor_variants


class SyntheticArteContext(unittest.TestCase):
    def test_record_index_selects_shared_stream_variant(self):
        expected = [b"ARTE158", b"ARTE159"]
        parts = factor_variants(expected, "compact")
        book = build_book(parts, "compact")
        encoded = encode_parts(parts, "compact", book)
        image = bytearray(0x800000)
        start = 0x2C0000
        image[start:start + len(encoded)] = encoded
        bindings, fits = [], []
        for index, raw, selection in ((158, expected[0], 11), (159, expected[1], 13)):
            storage = ARTE_TABLE_OFFSET + index * ARTE_STRIDE
            pointer = 0x08000000 + start
            struct.pack_into("<I", image, storage, pointer)
            binding_id = f"ARTE_{index:03d}:{storage:08X}"
            bindings.append(dict(id=f"ARTE_{index:03d}", binding_id=binding_id,
                jp_pointer_storage=str(storage), jp_pointer_value=str(pointer),
                category="compact", slot_capacity=str(len(encoded)),
                latest_ko_hash=hashlib.sha256(raw).hexdigest()))
            fits.append(dict(binding_id=binding_id, encoded_length=str(len(encoded)),
                native_output_length=str(len(raw) + 1), inline_part_count="4",
                inline_selection=str(selection)))
        outputs = [decode_name(image, index, 0, bindings, fits, book)
                   for index in (158, 159, 159, 158)]
        self.assertEqual(outputs, [expected[0] + b"\0", expected[1] + b"\0",
                                   expected[1] + b"\0", expected[0] + b"\0"])
        with self.assertRaises(ValueError):
            decode_name(image, 158, 1, bindings, fits, book)
        for index in (-1, 232):
            with self.assertRaises(ValueError):
                decode_name(image, index, 0, bindings, fits, book)


if __name__ == "__main__":
    unittest.main()

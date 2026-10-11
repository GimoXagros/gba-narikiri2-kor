"""Negative strict-layout tests, including the exact 8MiB output invariant."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from strict_layout_core import (Binding, ROM_SIZE, Write, assemble_fixed,
                                slot_write, validate_bindings, verify_decoded)


def native_decode(image, start, end, capacity):
    stop = image.find(b"\0", start, end)
    if stop < 0:
        raise ValueError("Unterminated bounded string")
    output = image[start:stop+1]
    if len(output) > capacity:
        raise ValueError("Output buffer overflow")
    return output


class StrictLayoutTests(unittest.TestCase):
    def setUp(self):
        source = bytearray(b"\xff" * ROM_SIZE)
        source[0x100:0x104] = (0x08000200).to_bytes(4, "little")
        source[0x104:0x108] = (0x08000200).to_bytes(4, "little")
        source[0x200:0x208] = b"source!\0"
        self.source = bytes(source)
        self.row = Binding("A", 0x100, self.source[0x100:0x104],
                           0x200, 0x208, b"target\0")

    def write(self, stream=b"target\0"):
        return slot_write(self.source, self.row, stream, encoding="STRICT_DIRECT",
                          consumer="synthetic bounded C reader", provenance="test fixture")

    def test_fixed_image_and_alias_roundtrip(self):
        alias = Binding("B", 0x104, self.source[0x104:0x108],
                        0x200, 0x208, b"target\0")
        target, manifest = assemble_fixed(self.source, [self.write()], [self.row, alias])
        self.assertEqual(len(target), ROM_SIZE)
        self.assertEqual(target[0x100:0x108], self.source[0x100:0x108])
        self.assertEqual(target[0x207], self.source[0x207])
        self.assertEqual(verify_decoded(target, [self.row, alias], native_decode)
                         ["pointer_bindings_total"], 2)
        self.assertEqual(manifest[0]["start"], self.row.start)

    def test_wrong_pointer_rejected(self):
        target = bytearray(self.source)
        target[0x100] ^= 4
        with self.assertRaisesRegex(ValueError, "pointer"):
            verify_decoded(bytes(target), [self.row], native_decode)

    def test_one_byte_slot_overflow_rejected(self):
        with self.assertRaisesRegex(ValueError, "slot overflow"):
            self.write(b"12345678\0")

    def test_divergent_alias_rejected(self):
        other = Binding("B", 0x104, self.source[0x104:0x108],
                        0x200, 0x208, b"different\0")
        with self.assertRaisesRegex(ValueError, "ALIAS_SEMANTIC_CONFLICT"):
            assemble_fixed(self.source, [self.write()], [self.row, other])

    def test_omitted_translation_rejected(self):
        with self.assertRaises(ValueError):
            verify_decoded(self.source, [self.row], native_decode)

    def test_output_buffer_overflow_rejected(self):
        with self.assertRaisesRegex(ValueError, "Output buffer overflow"):
            native_decode(self.source, 0x200, 0x208, 7)

    def test_missing_terminator_rejected(self):
        target, _ = assemble_fixed(self.source, [self.write(b"12345678")], [self.row])
        with self.assertRaisesRegex(ValueError, "Unterminated"):
            verify_decoded(target, [self.row], native_decode)

    def test_pointer_owner_write_rejected(self):
        write = Write("bad", 0x100, self.source[0x100:0x104], b"xxxx", "test",
                      "test", "test", ("test",))
        with self.assertRaisesRegex(ValueError, "protected text pointer"):
            assemble_fixed(self.source, [write], [self.row])

    def test_overlapping_and_unowned_writes_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlapping"):
            assemble_fixed(self.source, [self.write(), Write("overlap", 0x201,
                self.source[0x201:0x204], b"bad", "test", "test", "test", ("test",))], [self.row])
        with self.assertRaisesRegex(ValueError, "ownership"):
            assemble_fixed(self.source, [Write("unknown", 0x300, b"\xff", b"x",
                "", "", "", ())], [self.row])

    def test_empty_denominator_rejected(self):
        with self.assertRaisesRegex(ValueError, "Empty"):
            assemble_fixed(self.source, [], [])

    def test_wrong_source_extent_and_expected_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError, "8MiB"):
            assemble_fixed(self.source+b"x", [], [self.row])
        bad = Write("bad", 0x300, b"\x00", b"x", "test", "test", "test", ("test",))
        with self.assertRaisesRegex(ValueError, "expected source bytes"):
            assemble_fixed(self.source, [bad], [self.row])


if __name__ == "__main__":
    unittest.main()

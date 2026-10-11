"""Public invariants for the fixed-size diagnostic linker; no private ROM."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from strict_runtime_linker import (Ledger, Segment, ROM_BASE, ROM_SIZE,
    relocate_address, relocate_code_literals, scan_changed_expanded_refs)


class FixedLinkerTests(unittest.TestCase):
    def test_guarded_stages_reject_wrong_source_and_same_stage_overlap(self):
        source = bytes(ROM_SIZE)
        link = Ledger(source)
        link.put("adopted", 100, b"\0\0", b"ab", stage=1, evidence="source")
        link.put("probe", 100, b"ab", b"cd", stage=2, evidence="manifest")
        self.assertEqual(link.image[100:102], b"cd")
        with self.assertRaisesRegex(ValueError, "guard"):
            link.put("bad", 100, b"ab", b"ef", stage=3, evidence="stale")
        with self.assertRaisesRegex(ValueError, "collision"):
            link.put("collision", 100, b"cd", b"ef", stage=2, evidence="same")
        with self.assertRaisesRegex(ValueError, "extent"):
            link.put("outside", ROM_SIZE, b"\0", b"x", stage=3, evidence="outside")

    def test_code_relocation_only_maps_named_literal_targets(self):
        old, new = 0xC00500, 0xB9600
        segment = Segment("banked_decode", old, new, 52, "code")
        image = struct.pack("<IIII", 0x11111111, ROM_BASE + old + 1,
                            ROM_BASE + 0xC0D672, 0x22222222)
        moved, resolved, open_refs = relocate_code_literals(image, segment, [segment])
        self.assertEqual(struct.unpack_from("<I", moved, 4)[0], ROM_BASE + new + 1)
        self.assertEqual(struct.unpack_from("<I", moved, 8)[0], ROM_BASE + 0xC0D672)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(len(open_refs), 1)
        self.assertIsNone(relocate_address(ROM_BASE + 0xC06000, [segment]))

    def test_unchanged_pointer_shape_is_not_called_a_reference(self):
        source = bytearray(ROM_SIZE)
        struct.pack_into("<I", source, 0x200, ROM_BASE + 0xC00501)
        final = bytearray(source)
        struct.pack_into("<I", final, 0x204, ROM_BASE + 0xC00501)
        segment = Segment("banked_decode", 0xC00500, 0xB9600, 52, "code")
        mapped, open_refs = scan_changed_expanded_refs(source, final, [segment])
        self.assertEqual([hit["at"] for hit in mapped], [0x204])
        self.assertEqual(open_refs, [])

    def test_census_catches_expansion_refs_beyond_prior_decoder_arena(self):
        # Real omitted map tables were CA4000/CA4220: an arena-limited scan
        # missed them and the 8 MiB cartridge mirrored unrelated bytes.
        source = bytes(ROM_SIZE)
        final = bytearray(source)
        pointers = (0x08800000, 0x08CA4000, 0x08CA4220, 0x09FFFFFF)
        for i,value in enumerate(pointers):
            struct.pack_into('<I',final,0xCA00+i*4,value)
        struct.pack_into('<I',final,0xCA10,0x0A000000)
        mapped, unresolved = scan_changed_expanded_refs(source, final, [])
        self.assertEqual(mapped, [])
        self.assertEqual([r['value'] for r in unresolved], list(pointers))


if __name__ == "__main__":
    unittest.main()

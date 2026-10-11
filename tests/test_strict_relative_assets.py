"""Synthetic ownership guards for in-place relative graphic resources."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from strict_relative_assets import TABLES, plan, read_resource
from narikiri2_item_ui_font import compress_lz77


def literal_lz(raw):
    out = bytearray([0x10, len(raw)&255, len(raw)>>8&255,
                     len(raw)>>16&255])
    for index in range(0, len(raw), 8):
        out.append(0)
        out.extend(raw[index:index+8])
    return bytes(out)


def images(old, new):
    original = bytearray(0x3AC000)
    adopted = bytearray(original)
    for table, count in TABLES:
        struct.pack_into("<I", original, table, count)
        struct.pack_into("<I", adopted, table, count)
    table, count = TABLES[-1]
    old_start, new_start = 0x3AA000, 0x3AB000
    at = table+4+4*(count-1)
    struct.pack_into("<I", original, at, old_start-table)
    struct.pack_into("<I", adopted, at, new_start-table)
    original[old_start:old_start+len(old)] = old
    adopted[new_start:new_start+len(new)] = new
    return original, adopted, at, old_start


class RelativeAssetPlan(unittest.TestCase):
    def test_changed_resource_replaces_only_original_owned_stream_and_relative(self):
        old_native, new_native = bytes(range(64)), bytes([7])*64
        japanese, adopted, at, old_start = images(
            literal_lz(old_native), literal_lz(new_native))
        writes, records = plan(japanese, adopted)
        self.assertEqual(len(writes), 2)
        self.assertEqual(len(records), 1)
        self.assertEqual({write.start for write in writes}, {at, old_start})
        self.assertEqual(records[0]["index"], TABLES[-1][1]-1)
        result = bytearray(japanese)
        for write in writes:
            self.assertEqual(result[write.start:write.end], write.before)
            result[write.start:write.end] = write.after
        self.assertEqual(read_resource(result, old_start)[0], new_native)
        self.assertEqual(result[at:at+4], japanese[at:at+4])

    def test_native_geometry_and_original_capacity_fail_closed(self):
        japanese, adopted, _, _ = images(literal_lz(bytes(range(64))),
                                         literal_lz(bytes([1])*63))
        with self.assertRaisesRegex(ValueError, "geometry"):
            plan(japanese, adopted)
        japanese, adopted, _, _ = images(compress_lz77(bytes(64), vram_safe=True),
                                         literal_lz(bytes(range(64))))
        with self.assertRaisesRegex(ValueError, "consumed extent"):
            plan(japanese, adopted)

    def test_externally_owned_map_hint_is_not_written_by_relative_planner(self):
        japanese, adopted, _, _ = images(literal_lz(bytes(range(64))),
                                         literal_lz(bytes([2])*64))
        table = 0x380F08
        at = table+4+6*4
        struct.pack_into("<I", adopted, at, 0x10000)
        writes, records = plan(japanese, adopted)
        self.assertEqual(len(records), 1)
        self.assertNotIn(at, {write.start for write in writes})


if __name__ == "__main__":
    unittest.main()

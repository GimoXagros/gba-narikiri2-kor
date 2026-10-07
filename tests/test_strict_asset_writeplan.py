"""Real-source checks for the two title assets that fit their JP slots."""
from pathlib import Path
import csv
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from find_gba_lz77_asset import decompress_lz77_stream
from strict_asset_writeplan import (RESOURCES, TABLE, plan_credits_relocation, plan_small_font,
                                    plan_staff_font_relocation, plan_title_assets,
                                    title_veneer_owner, validate_reclaimed_suffix,
                                    _direct_pointer_hits, _table_starts)

SOURCE = ROOT.parent / "narikiri2-v09d-graphics-test"
JP = SOURCE / "Japanese.gba"
KO = SOURCE / ("private_validation/listperf-20261002/root/credits-build-a/"
               "Xagros_Narikiri2_KOR_v1.0_listperf-pass01_credits_TEST.gba")


class SyntheticAssetGuards(unittest.TestCase):
    def test_reclaimed_suffix_rejects_compressed_input_and_collisions(self):
        validate_reclaimed_suffix(0x100, 0x200, ((0x110, 0x120), (0x130, 0x150)))
        with self.assertRaisesRegex(ValueError, "outside reclaimed"):
            validate_reclaimed_suffix(0x100, 0x200, ((0x0F0, 0x120),))
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            validate_reclaimed_suffix(0x100, 0x200,
                                      ((0x110, 0x140), (0x130, 0x150)))

    def test_relative_table_order_and_interior_pointer_audit(self):
        image = bytearray(b"\0" * 0x800000)
        for index in range(19):
            storage = TABLE + 4 + index * 4
            image[storage:storage+4] = (0x100 + index * 0x20).to_bytes(4, "little")
        self.assertEqual(_table_starts(image, ordered=True)[0], TABLE + 0x100)
        image[0x100:0x104] = (0x08020004).to_bytes(4, "little")
        self.assertEqual(_direct_pointer_hits(image, 0x20000, 0x20010), [0x100])
        image[TABLE+8:TABLE+12] = (0x100).to_bytes(4, "little")
        with self.assertRaisesRegex(ValueError, "ownership"):
            _table_starts(image, ordered=True)


@unittest.skipUnless(JP.exists() and KO.exists(), "private source ROMs unavailable")
class TitleAssetPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jp, cls.ko = JP.read_bytes(), KO.read_bytes()

    def test_in_place_streams_preserve_relative_pointers_and_decode(self):
        writes, report = plan_title_assets(self.jp, self.ko)
        self.assertEqual([w.start for w in writes], [0x37C09C, 0x37EBE8])
        self.assertEqual([len(w.after) for w in writes], [6364, 1134])
        self.assertEqual(report["total_written_bytes"], 7498)
        image = bytearray(self.jp)
        for write in writes:
            self.assertEqual(self.jp[write.start:write.end], write.before)
            image[write.start:write.end] = write.after
        for index, _, _, _, korean_start, _ in RESOURCES:
            storage = TABLE + 4 + index * 4
            self.assertEqual(image[storage:storage+4], self.jp[storage:storage+4])
            target = TABLE + struct.unpack_from("<I", image, storage)[0]
            actual, _ = decompress_lz77_stream(image, target, 0x20000)
            expected, _ = decompress_lz77_stream(self.ko, korean_start, 0x20000)
            self.assertEqual(actual, expected)
        self.assertEqual(image[0xA1E4:0xA1E8], self.jp[0xA1E4:0xA1E8])

    def test_wrong_source_identity_rejected(self):
        bad = bytearray(self.jp)
        bad[0x100] ^= 1
        with self.assertRaisesRegex(ValueError, "Japanese source identity"):
            plan_title_assets(bytes(bad), self.ko)

    def test_bounded_near_veneer_suffix(self):
        owner = title_veneer_owner(self.jp, self.ko)
        self.assertEqual((owner["start"], owner["end"]), (0x37D980, 0x37D990))
        self.assertTrue(owner["caller_0801C3B4_thumb_bl_reachable"])
        self.assertEqual(owner["jp_expected_bytes"], "6c5779cb6c149785bb0cb1bbbbcbb3bc")
        self.assertEqual(owner["diagnostic_expected_bytes"], "0e009799995901999914009999040099")

    def test_korean_small_font_fits_native_font_stream(self):
        write, report = plan_small_font(self.jp, self.ko)
        self.assertEqual((write.start, len(write.after)), (0xCA3F4, 1564))
        self.assertEqual(report["direct_pointer_storages"], [0x2158, 0x21D4])
        image = bytearray(self.jp)
        image[write.start:write.end] = write.after
        for storage in (0x2158, 0x21D4):
            self.assertEqual(image[storage:storage+4], self.jp[storage:storage+4])
        actual, used = decompress_lz77_stream(image, write.start, 0x10000)
        expected, _ = decompress_lz77_stream(self.ko, 0xC18000, 0x10000)
        self.assertEqual((actual, used), (expected, 1564))

    def test_native_staff_font_and_wrapper_fit_title_suffix(self):
        writes, report = plan_staff_font_relocation(self.jp, self.ko)
        self.assertEqual(report["font_bytes"], 1997)
        self.assertEqual(report["wrapper_bytes"], 52)
        self.assertEqual(report["hook_after"], "004b1847a1d93708")
        self.assertEqual(len(writes), 3)
        image = bytearray(self.jp)
        for write in writes:
            self.assertEqual(image[write.start:write.end], write.before)
            image[write.start:write.end] = write.after
        actual, used = decompress_lz77_stream(image, 0x37D9E0, 0x10000)
        native, _ = decompress_lz77_stream(self.jp, 0xCA3F4, 0x10000)
        self.assertEqual((actual, used), (native, 1997))
        self.assertEqual(image[0x37D9A0:0x37D9A0+52], writes[1].after)

    def test_credits_table_and_strings_fit_copyright_suffix(self):
        writes, report = plan_credits_relocation(self.jp, self.ko)
        self.assertEqual((report["payload_bytes"], report["table_rows"],
                          report["relocated_string_pointers"]), (873, 199, 7))
        self.assertEqual((writes[0].start, writes[0].end), (0x37F058, 0x37F3C1))
        image = bytearray(self.jp)
        for write in writes:
            self.assertEqual(image[write.start:write.end], write.before)
            image[write.start:write.end] = write.after
        self.assertEqual(struct.unpack_from("<I", image, 0xA56E8)[0], 0x0837F058)
        pointers = [struct.unpack_from("<I", image, 0x37F058+4*i)[0]
                    for i in range(200)]
        self.assertEqual(pointers[199], 0)
        self.assertEqual(image[0x37F058:0x37F058+191*4],
                         self.jp[0x7F9608:0x7F9904])
        self.assertTrue(all(0x0837F058 <= value < 0x0837F3C1
                            for value in pointers[192:199]))

    def test_planned_owners_do_not_overlap_frozen_text_slots_or_pointer_words(self):
        catalog = SOURCE / "private_validation/strict-layout-20261003/TEXT_BINDINGS.csv"
        if not catalog.exists():
            self.skipTest("frozen private text catalog unavailable")
        title_writes, _ = plan_title_assets(self.jp, self.ko)
        font_write, _ = plan_small_font(self.jp, self.ko)
        staff_writes, _ = plan_staff_font_relocation(self.jp, self.ko)
        credits_writes, _ = plan_credits_relocation(self.jp, self.ko)
        spans = [(w.start, w.end) for w in title_writes + [font_write]
                 + staff_writes + credits_writes]
        spans.append((0x37D980, 0x37D990))
        with catalog.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                start, end = int(row["jp_text_start"]), int(row["proven_slot_end"])
                storage = int(row["jp_pointer_storage"])
                for lo, hi in spans:
                    self.assertFalse(start < hi and end > lo, row["binding_id"])
                    self.assertFalse(storage < hi and storage + 4 > lo, row["binding_id"])


if __name__ == "__main__":
    unittest.main()

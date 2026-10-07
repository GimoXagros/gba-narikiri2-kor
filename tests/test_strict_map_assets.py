"""Synthetic map-relative resource and frame restoration regressions."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from strict_map_assets import plan
from strict_relative_assets import read_resource
from narikiri2_item_ui_font import compress_lz77
from tests.test_strict_relative_assets import literal_lz

TABLE, NEW_TABLE = 0x380F08, 0xCA4000
LABELS, NEW_LABELS = 0x2C23B8, 0xCA4220


def putword(image, at, value):
    struct.pack_into("<I", image, at, value & 0xFFFFFFFF)


def source_images():
    japanese = bytearray(0x800000)
    adopted = bytearray(0xCB0000)
    putword(japanese, TABLE, 135)
    putword(adopted, TABLE, 135)
    putword(adopted, NEW_TABLE, 135)
    putword(japanese, 0xCAEC, LABELS+0x08000000)
    putword(japanese, 0xCAF0, TABLE+0x08000000)
    putword(adopted, 0xCAEC, NEW_LABELS+0x08000000)
    putword(adopted, 0xCAF0, NEW_TABLE+0x08000000)

    for index in range(135):
        if index < 9:
            old = 0x381400+index*0x100
        elif index <= 31:
            old = 0x382000+(index-9)*76
        else:
            old = 0x390000+(index-32)*64
        putword(japanese,TABLE+4+4*index,old-TABLE)
        prior = old
        new = old
        if index in (6,7):
            prior = (0xCA5718 if index == 6 else 0xCA5780)
            new = (0xCA57A8 if index == 6 else 0xCA5810)
            raw = bytes([index])*64
            japanese[old:old+76] = literal_lz(bytes(range(64)))
            new_packed = compress_lz77(raw,vram_safe=True)
            prior_packed = compress_lz77(bytes([index+20])*64,vram_safe=True)
            adopted[new:new+len(new_packed)] = new_packed
            adopted[prior:prior+len(prior_packed)] = prior_packed
        elif 9 <= index <= 30:
            new = 0xCA4300+(index-9)*96
            japanese[old:old+76] = literal_lz(bytes(range(64)))
            adopted[new:new+76] = literal_lz(bytes([index])*64)
        putword(adopted,TABLE+4+4*index,prior-TABLE)
        putword(adopted,NEW_TABLE+4+4*index,new-NEW_TABLE)

    # Four separately bounded title-resource suffixes are optional map arenas.
    for index in (10,13,14,15):
        old = 0x376B00+index*128
        putword(japanese,0x3768FC+index*4,old-0x3768F8)
        putword(adopted,0x3768FC+index*4,old-0x3768F8)
        japanese[old:old+76] = literal_lz(bytes(range(64)))
        adopted[old:old+76] = literal_lz(bytes([index])*64)

    # Twenty-two distinct original rows own their frame and layout objects.
    for row in range(25):
        old_row, new_row = LABELS+row*8, NEW_LABELS+row*8
        if row < 3:
            japanese[old_row:old_row+8] = adopted[new_row:new_row+8] = b"\0"*8
            continue
        old_frame, new_frame = 0x2C3000+row*16, 0xCA6000+row*16
        old_layout, new_layout = 0x2C4000+row*16, 0xCA6800+row*16
        putword(japanese,old_row,old_frame+0x08000000)
        putword(japanese,old_row+4,row)
        putword(adopted,new_row,new_frame+0x08000000)
        putword(adopted,new_row+4,row+100)
        putword(japanese,old_frame,1)
        putword(japanese,old_frame+4,old_layout+0x08000000)
        putword(adopted,new_frame,1)
        putword(adopted,new_frame+4,new_layout+0x08000000)
        putword(japanese,old_layout,1)
        putword(adopted,new_layout,1)
        putword(japanese,old_layout+4,row)
        putword(adopted,new_layout+4,row+100)
    return japanese, adopted


class MapAssetPlan(unittest.TestCase):
    def test_relocated_sprites_and_frames_return_to_owned_originals(self):
        japanese, adopted = source_images()
        writes, report = plan(japanese, adopted)
        self.assertEqual({record["index"] for record in report["resources"]},
                         set(range(9,31)))
        self.assertEqual(len(report["layouts"]), 22)
        result = bytearray(japanese)
        for write in writes:
            self.assertEqual(result[write.start:write.end], write.before)
            result[write.start:write.end] = write.after
        for record in report["resources"]:
            index = record["index"]
            relative = struct.unpack_from("<I", result, TABLE+4+index*4)[0]
            self.assertEqual((TABLE+relative)&0xFFFFFFFF, record["start"])
            self.assertEqual(read_resource(result,record["start"])[0],
                             bytes([index])*64)
        for index in (6,7):
            old = (TABLE+struct.unpack_from("<I",japanese,TABLE+4+index*4)[0])&0xFFFFFFFF
            self.assertEqual(read_resource(result,old)[0],bytes([index])*64)
        for row in range(3,25):
            old_row=LABELS+8*row
            frame=struct.unpack_from("<I",result,old_row)[0]-0x08000000
            layout=struct.unpack_from("<I",result,frame+4)[0]-0x08000000
            self.assertEqual(struct.unpack_from("<I",result,layout+4)[0],row+100)
        self.assertEqual(result[0xCAEC:0xCAF4],japanese[0xCAEC:0xCAF4])

    def test_unclassified_target_or_absolute_pool_reference_fails_closed(self):
        japanese, adopted = source_images()
        putword(adopted,NEW_TABLE+4+50*4,0x1234)
        with self.assertRaisesRegex(ValueError,"Unclassified map resource"):
            plan(japanese,adopted)
        japanese, adopted = source_images()
        putword(japanese,0x200000,0x08000000+0x382000+2)
        with self.assertRaisesRegex(ValueError,"Unclassified absolute map-pool reference"):
            plan(japanese,adopted)


if __name__ == "__main__":
    unittest.main()

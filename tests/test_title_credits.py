"""Contract checks for the appended credits and protected title resources."""
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_title_credits as subject
from gba_rl import decompress
from find_gba_lz77_asset import decompress_lz77_stream
from bps import create_bps,apply_bps,BpsError


class GlyphContract(unittest.TestCase):
    def test_full_copyright_line_fits_actual_upper_sprite_coverage(self):
        points,width=subject.copyright_points('© 이노마타 무츠미  © 후지시마 코스케')
        actual={(x+(240-width)//2,y+137) for x,y in points}
        self.assertTrue(all(8<=x<200 and 128<=y<149 for x,y in subject.expanded(actual,1)))

    def test_missing_glyph_fails_instead_of_silent_substitution(self):
        with self.assertRaisesRegex(ValueError,'Missing copyright glyph'):
            subject.copyright_points('힣')


@unittest.skipUnless((ROOT/'private_validation/japanese.gba').exists(),'private Japanese ROM required')
class ProductContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jp=(ROOT/'private_validation/japanese.gba').read_bytes()
        cls.base=(ROOT/'private_validation/v09d-release-a/Xagros_Narikiri2_KOR_v0.9d.gba').read_bytes()
        cls.rom,cls.report=subject.build(cls.base,cls.jp)

    def test_staff_table_keeps_every_original_row_then_appends_in_order(self):
        pointer=struct.unpack_from('<I',self.rom,0xA56E8)[0]-0x08000000
        pointers=[]
        while True:
            address=struct.unpack_from('<I',self.rom,pointer+len(pointers)*4)[0]
            if not address:break
            pointers.append(address)
            self.assertLess(len(pointers),220)
        self.assertEqual(len(pointers),196)
        self.assertEqual(struct.pack('<191I',*pointers[:191]),self.jp[0x7F9608:0x7F9904])
        tail=[]
        for value in pointers[191:]:
            at=value-0x08000000
            tail.append(self.rom[at:self.rom.index(0,at)].decode('ascii'))
        self.assertEqual(tail,['','','KOREAN TRANSLATION','TEAM FFR','XAGROS'])
        self.assertEqual(self.rom[0xA5316:0xA5318],bytes.fromhex('3a21'))

    def test_ribbon_emblem_and_year_line_are_protected(self):
        for index,source in ((9,0x37C09C),(16,0x37EBE8)):
            at=subject.TABLE+struct.unpack_from('<I',self.rom,subject.TABLE+4+index*4)[0]
            raw,_=decompress_lz77_stream(self.rom,at,0x20000)
            if index==9:
                reference=decompress(self.base,source)[0]
                old=subject.unpack(reference,subject.LOGO_SPRITES)
                new=subject.unpack(raw,subject.LOGO_SPRITES)
                self.assertEqual(new[0],old[0])
                # The shared backdrop may lose old white text-halo pixels;
                # actual emblem colors/interiors stay intact outside ®/2.
                for y in range(160):
                    for x in range(240):
                        numeral_region=(190<=x<216 and 26<=y<92) or (184<=x<193 and 75<=y<92)
                        if not numeral_region and (old[1][y][x] not in (0,6,7) or x>=192 or y<28 or y>=92):
                            self.assertEqual(new[1][y][x],old[1][y][x])
                # Stale hanging glow under the old lettering, observed in r2.
                for x,y in ((40,82),(42,82),(86,82)):
                    self.assertEqual(old[1][y][x],6)
                    self.assertEqual(new[1][y][x],0)
                # New edge under the corrected final letter gets a white rim.
                self.assertEqual(new[1][84][173],6)
                self.assertTrue(all(new[2][y][131]==0 for y in range(40,79)))
                face={10,11,12,13,15}
                self.assertTrue(all(new[2][y][x] not in face for y in range(49,52) for x in (175,176)))
                self.assertTrue(any(new[2][y][175] in face for y in range(54,59)))
                # Japanese navy anti-aliasing replaces the pale blurred edge;
                # stray gold pixels above the numeral must not survive.
                self.assertEqual(new[2][40][213],8)
                self.assertTrue(all(new[2][28][x]==0 for x in range(190,216)))
                # Circle top and the R's open counter, at native pixel scale.
                self.assertEqual(new[2][75][188],9)
                self.assertEqual(new[2][78][187],1)
                self.assertTrue(all(new[2][y][x]==0 for y in range(84,92) for x in range(185,193)))
            else:
                original=subject.unpack(decompress(self.jp,source)[0],subject.COPYRIGHT_SPRITES)[3]
                actual=subject.unpack(raw,subject.COPYRIGHT_SPRITES)[3]
                self.assertEqual(actual[149:],original[149:])
        self.assertEqual(self.rom[0x3746D8:0x3746DC],self.base[0x3746D8:0x3746DC])

    def test_japanese_patch_roundtrip_and_wrong_input_rejection(self):
        patch=create_bps(self.jp,self.rom)
        self.assertEqual(apply_bps(self.jp,patch),self.rom)
        bad=bytearray(self.jp);bad[-1]^=1
        with self.assertRaises(BpsError):apply_bps(bytes(bad),patch)


if __name__=='__main__':unittest.main()

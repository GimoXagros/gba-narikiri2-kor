"""Exact palette round trip and real Thumb unpacking with stack/canary checks."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from strict_compact_font import pack_font,assemble,assemble_inspector
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB
from unicorn.arm_const import *


class CompactFontTests(unittest.TestCase):
    def test_all_nibbles_and_modes_cpu_exact_and_bounded(self):
        clear=bytes(((15 if (i+j)%3==0 else 0) | ((15 if (i+j)%5==0 else 0)<<4)) for j in range(16) for i in range(32))
        solid=bytes((b&15 or 11) | ((b>>4 or 11)<<4) for b in clear)
        bits,tables=pack_font(clear,solid)
        self.assertEqual((len(bits),len(tables)),(128,64))
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for base in (0x100000,0x200000,0x300000,0x400000):u.mem_map(base,0x1000)
        u.mem_write(0x100000,assemble('strict_compact_font_unpack.s',0x100000,FONT_COUNT=16,FONT_BITS=0x200000,FONT_NIBBLES=0x200800))
        u.mem_write(0x200000,bits);u.mem_write(0x200800,tables)
        for glyph,mode in [(g,m) for g in range(16) for m in range(2)]+[(16,0),(0,2)]:
            u.mem_write(0x300000,b'\xa5'*64)
            for reg,v in ((UC_ARM_REG_R0,glyph),(UC_ARM_REG_R1,0x300010),(UC_ARM_REG_R2,mode),(UC_ARM_REG_SP,0x400ff0),(UC_ARM_REG_LR,0x100801)):
                u.reg_write(reg,v)
            u.emu_start(0x100001,0x100800,count=1000)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x400ff0)
            self.assertEqual(bytes(u.mem_read(0x300000,16)),b'\xa5'*16)
            self.assertEqual(bytes(u.mem_read(0x300030,16)),b'\xa5'*16)
            if glyph<16 and mode<2:
                self.assertEqual(u.reg_read(UC_ARM_REG_R0),0x300010)
                self.assertEqual(bytes(u.mem_read(0x300010,32)),(solid if mode else clear)[glyph*32:(glyph+1)*32])
            else:
                self.assertEqual(u.reg_read(UC_ARM_REG_R0),0)
                self.assertEqual(bytes(u.mem_read(0x300010,32)),b'\xa5'*32)

    def test_reject_lossy_input_and_assemble_both_consumer_wrappers(self):
        for clear,solid in ((b'',b''),(b'\0'*31,b'\xbb'*31),(b'\x10'*32,b'\xbb'*32)):
            with self.assertRaises(ValueError):pack_font(clear,solid)
        self.assertLess(len(assemble('strict_compact_font_get_tile.s',0x08c00600,
            BANKED_DECODER=0x08c00501,FONT_UNPACKER=0x08c93401,TILE_CACHE=0x08c00801)),0x100)
        self.assertLess(len(assemble_inspector(0x08c1ec00,0x08c93400)),0x400)


if __name__=='__main__':unittest.main()

"""Independent pixel/ABI oracle for the reclaimed native bitmap converter."""
import random,struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_halfspace_prototype import ROOT,assemble
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB
from unicorn.arm_const import *


class BitmapConverterTests(unittest.TestCase):
    def test_all_source_bits_seeded_patterns_and_preserved_neighbours(self):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        u.mem_map(0x08000000,0x100000);u.mem_map(0x02000000,0x40000)
        body=assemble((ROOT/'asm/halfspace_bitmap_convert.s').read_text(),0x21fc)
        self.assertEqual(len(body),104)
        u.mem_write(0x080021fc,body)
        rng=random.Random(0xb17a95);dest=0x02002020;stack=0x0203f000;stop=0x08000200
        patterns=[[1<<bit]*16 for bit in range(16)]+[[rng.randrange(65536) for _ in range(16)] for _ in range(64)]
        saved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7)
        for rows in patterns:
            fill=rng.randbytes(192);expected=bytearray(fill)
            for y,row in enumerate(rows):
                for x in range(12):
                    at=32+(y//8)*64+(x//8)*32+(y%8)*4+(x%8)//2
                    shift=4*(x%2);value=15 if row&(1<<x) else 0
                    expected[at]=(expected[at]&~(15<<shift))|(value<<shift)
            u.mem_write(dest-32,fill)
            # Model the native wrapper's existing stack, including glyph32B.
            u.mem_write(stack,struct.pack('<5I',*[0x12340000+r for r in saved],stop|1)+struct.pack('<16H',*rows))
            u.reg_write(UC_ARM_REG_R0,dest);u.reg_write(UC_ARM_REG_SP,stack)
            for r in (UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):u.reg_write(r,0x12340000+r)
            u.emu_start(0x080021fd,stop,count=3000)
            self.assertEqual(bytes(u.mem_read(dest-32,192)),expected)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),stack+20)
            for r in saved+(UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):self.assertEqual(u.reg_read(r),0x12340000+r)


if __name__=='__main__':unittest.main()

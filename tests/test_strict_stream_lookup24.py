"""SBS2 lookup against sparse page boundaries and exact original bounds."""
from pathlib import Path
import random,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
from strict_stream_lookup24 import pack_bounds24,unpack_bounds24,assemble_lookup24
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB
from unicorn.arm_const import *


class Lookup24Tests(unittest.TestCase):
    def test_sparse_pages_odd_entry_offsets_boundaries_and_original_extent(self):
        rng=random.Random(0x6caa056)
        offsets=sorted(set([0,1,32767,32768,65535,0x7fff00]+rng.sample(range(0x7fff00),9246)))
        rows=[(0x08000000+at,rng.randrange(1,min(511,0x800000-at)+1)) for at in offsets]
        blob=pack_bounds24(rows);self.assertEqual(unpack_bounds24(blob),rows)
        self.assertLess(len(blob),len(rows)*4)
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        u.mem_map(0x100000,0x1000);u.mem_map(0x200000,0x10000);u.mem_map(0x300000,0x1000)
        u.mem_write(0x100000,assemble_lookup24(0x100000));u.mem_write(0x200000,blob)
        expected=dict(rows)
        queries=rows[::17]+[(0x02000000,0),(0x08800000,0),(0x08234567,expected.get(0x08234567,0))]
        queries += [(s+1,expected.get(s+1,0)) for s,_ in rows[::31]]
        for pointer,size in queries:
            for reg,value in ((UC_ARM_REG_R0,pointer),(UC_ARM_REG_R1,0x200000),(UC_ARM_REG_R2,len(rows)),
                              (UC_ARM_REG_SP,0x300f00),(UC_ARM_REG_LR,0x100801)):
                u.reg_write(reg,value)
            for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7):u.reg_write(reg,0x76543210)
            u.emu_start(0x100001,0x100800,count=500)
            self.assertEqual(u.reg_read(UC_ARM_REG_PC),0x100800)
            self.assertEqual(u.reg_read(UC_ARM_REG_R0),size)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x300f00)
            for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7):self.assertEqual(u.reg_read(reg),0x76543210)

    def test_structural_corruption_rejected(self):
        data=pack_bounds24([(0x08000000,5),(0x08008001,10)])
        for broken in (data[:-1],b'XXXX'+data[4:],data[:8]+b'\0'*4+data[12:],data[:18]+b'\xff\xff'+data[20:]):
            with self.assertRaises(ValueError):unpack_bounds24(broken)


if __name__=='__main__':unittest.main()

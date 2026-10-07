"""Real Thumb search with guard pages, exact-address and ABI checks."""
from pathlib import Path
import random,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from strict_stream_lookup import pack_bounds,assemble_lookup
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import *


class StreamLookupTests(unittest.TestCase):
    def test_binary_search_sparse_table_bounded_and_exact(self):
        rng=random.Random(61261)
        offsets=sorted(rng.sample(range(0,0x7fff00,4),8203))
        rows=[(0x08000000+x,rng.randrange(1,256)) for x in offsets]
        packed=pack_bounds(rows)
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        u.mem_map(0x100000,0x1000);u.mem_map(0x200000,0x10000);u.mem_map(0x300000,0x1000)
        u.mem_write(0x100000,assemble_lookup(0x100000))
        table=0x210000-len(packed);u.mem_write(table,packed)
        instructions=[]
        def watch(uc,address,size,_):
            instructions.append(address)
            if address==0x100800:uc.emu_stop()
        u.hook_add(UC_HOOK_CODE,watch)
        queries=rows[::31]+[(0x02000000,0),(0x087fffff,0),(0x08800000,0)]
        queries += [(start+1,0) for start,_ in rows[::97]]
        for start,expected in queries:
            u.reg_write(UC_ARM_REG_R0,start);u.reg_write(UC_ARM_REG_R1,table);u.reg_write(UC_ARM_REG_R2,len(rows))
            for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7):u.reg_write(reg,0xface1234)
            u.reg_write(UC_ARM_REG_SP,0x300ff0);u.reg_write(UC_ARM_REG_LR,0x100801)
            instructions.clear();u.emu_start(0x100001,0x100802,count=1000)
            self.assertEqual(u.reg_read(UC_ARM_REG_R0),expected)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x300ff0)
            self.assertLess(len(instructions),230)
            for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7):self.assertEqual(u.reg_read(reg),0xface1234)

    def test_metadata_rejects_zero_duplicate_overflow_and_nonrom(self):
        for rows in ([],[(0x08000000,0)],[(0x08000000,512)],[(0x087fffff,2)],[(0x02000000,1)],[(0x08000000,1)]*2):
            with self.assertRaises(ValueError):pack_bounds(rows)


if __name__=='__main__':unittest.main()

"""Independent nibble oracle and ABI checks for the diagnostic compositor."""
import random
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_halfspace_prototype import ROOT,DRAW,assemble,helpers,REVIEWED_RUNTIME_SPANS,validate_runtime_spans
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB
from unicorn.arm_const import *


class HalfspacePrototypeTests(unittest.TestCase):
    def test_generated_owner_metadata_cannot_expand_native_write_permissions(self):
        writes=[('reviewed',a,bytes(b-a)) for a,b in REVIEWED_RUNTIME_SPANS]
        validate_runtime_spans(writes)
        for index in (0,1,2,10,len(writes)-1):
            changed=list(writes);name,at,payload=changed[index]
            changed[index]=(name,at,payload+b'\0\0')
            with self.assertRaises(ValueError):validate_runtime_spans(changed)
        with self.assertRaises(ValueError):validate_runtime_spans(writes+[("unexpected",0xCAB58,b'\0\0')])

    def cpu(self):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for at,size in ((0x08000000,0x100000),(0x02000000,0x40000),(0x03000000,0x8000)):
            u.mem_map(at,size)
        code,entries=helpers()
        u.mem_write(0x08000000+entries['draw'],code)
        u.mem_write(0x08000000+DRAW,assemble((ROOT/'asm/halfspace_full_draw.s').read_text().replace('ALIGNED_FAST',str(0x08000001+entries['aligned_fast'])).replace('SHARED_LUT',str(0x08002244)),DRAW))
        u.mem_write(0x080021fc,assemble((ROOT/'asm/halfspace_bitmap_convert.s').read_text(),0x21fc))
        return u

    def test_all_subtile_positions_widths_backgrounds_and_neighbours(self):
        rng=random.Random(0x6A1F)
        u=self.cpu()
        for odd in (0,1):
            for phase in (0,1):
                for space in (0,1):
                    for bg in range(16):
                        rows=[0]*16 if space else [rng.randrange(65536) for _ in range(16)]
                        fill=rng.randbytes(0x600);expected=bytearray(fill)
                        width=6 if space else 12
                        for y,row in enumerate(rows):
                            for x in range(width):
                                xx=x+4*odd+6*phase
                                at=0x100+(y//8)*0x3c0+(y%8)*4+(xx//8)*32+(xx%8)//2
                                shift=(xx%2)*4
                                value=15 if row&(1<<x) else bg
                                expected[at]=(expected[at]&~(15<<shift))|(value<<shift)
                        u.mem_write(0x03000200,fill)
                        u.mem_write(0x02000000,struct.pack('<16H',*rows))
                        u.mem_write(0x03000046,bytes([phase+2*space]))
                        u.mem_write(0x0300145a,bytes([bg]))
                        for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7):u.reg_write(reg,0x12340000+reg)
                        for reg,value in ((UC_ARM_REG_R0,0x03000300),(UC_ARM_REG_R1,0x02000000),(UC_ARM_REG_SP,0x0203f000),(UC_ARM_REG_LR,0x08000101)):
                            u.reg_write(reg,value)
                        u.emu_start(0x08000001+DRAW+8*odd,0x08000100,count=10000)
                        self.assertEqual(bytes(u.mem_read(0x03000200,0x600)),expected)
                        self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x0203f000)
                        for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7):self.assertEqual(u.reg_read(reg),0x12340000+reg)

    def test_advance_carries_half_cell_and_preserves_saved_registers(self):
        code,entries=helpers()
        u=self.cpu();u.mem_write(0x08000000+entries['draw'],code)
        for flags,expected_col,expected_phase in ((0,5,0),(1,5,1),(2,4,1),(3,5,0)):
            u.mem_write(0x03000044,bytes([4,0,flags]))
            u.reg_write(UC_ARM_REG_LR,0x08000101)
            u.emu_start(0x08000001+entries['advance'],0x08000100,count=100)
            self.assertEqual(bytes(u.mem_read(0x03000044,3)),bytes([expected_col,0,expected_phase]))

    def test_native_reset_entry_all_phase_flags_and_coordinates(self):
        for selective in (False,True):
            code,entries=helpers(selective=selective)
            u=self.cpu();u.mem_write(0x08000000+entries['draw'],code)
            u.mem_write(0x08001710,b'\x00\x4b\x18\x47'+struct.pack('<I',0x08000001+entries['reset']))
            for flags in range(4):
                for x,y in ((0,0),(3,2),(17,1)):
                    u.mem_write(0x03000040,bytes([1,1,19,4,9,3,flags,13,0,0,0,0]))
                    saved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
                    for reg in saved:u.reg_write(reg,0x12340000+reg)
                    for reg,value in ((UC_ARM_REG_R0,x),(UC_ARM_REG_R1,y),(UC_ARM_REG_LR,0x08000101),(UC_ARM_REG_SP,0x0203f000)):
                        u.reg_write(reg,value)
                    u.emu_start(0x08001711,0x08000100,count=100)
                    self.assertEqual(bytes(u.mem_read(0x03000044,3)),bytes([1+x,1+y,0]))
                    self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x0203f000)
                    for reg in saved:self.assertEqual(u.reg_read(reg),0x12340000+reg)


if __name__=='__main__':unittest.main()


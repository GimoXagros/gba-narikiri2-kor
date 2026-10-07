"""Synthetic independent pixel oracle; no private glyph/ROM assets required."""
import random,struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from strict_perf_full_draw_fast_8m import assemble,SOURCE,SLOT,build
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB
from unicorn.arm_const import (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R4,
    UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,
    UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC)

SAVED=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
       UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
DEST=0x06001000
GLYPH=0x02000100
RETURN=0x080A0000
STACK=0x0203F000


class FastDrawTests(unittest.TestCase):
    def cpu(self):
        uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for at,size in ((0x08000000,0x800000),(0x02000000,0x40000),
                        (0x03000000,0x8000),(0x06000000,0x20000)):
            uc.mem_map(at,size)
        code=assemble(SOURCE.read_text(encoding='utf-8'),SLOT[0])
        self.assertEqual(len(code),328)
        uc.mem_write(0x08000000+SLOT[0],code)
        return uc

    def prepare(self,uc,rows,bg,fill):
        uc.mem_write(GLYPH,struct.pack('<16H',*rows))
        uc.mem_write(DEST-0x100,fill)
        uc.mem_write(0x0300145A,bytes([bg]))
        for reg in SAVED:uc.reg_write(reg,0x12340000+reg)
        for reg,value in ((UC_ARM_REG_R0,DEST),(UC_ARM_REG_R1,GLYPH),
                          (UC_ARM_REG_SP,STACK),(UC_ARM_REG_LR,RETURN|1)):
            uc.reg_write(reg,value)

    def registers(self,uc):
        self.assertEqual(uc.reg_read(UC_ARM_REG_SP),STACK)
        for reg in SAVED:self.assertEqual(uc.reg_read(reg),0x12340000+reg)

    def test_pixels_neighbors_and_abi_against_independent_oracle(self):
        uc=self.cpu();rng=random.Random(0xFA57D2A)
        patterns=[[0]*16,[0xFFFF]*16,*[[1<<bit]*16 for bit in range(16)],
                  *[[rng.randrange(65536) for _ in range(16)] for _ in range(16)]]
        for odd in (0,1):
            for rows in patterns:
                for bg in range(16):
                    fill=rng.randbytes(0x500);expected=bytearray(fill)
                    for y,row in enumerate(rows):
                        for x in range(12):
                            xx=x+4*odd
                            at=0x100+(y//8)*0x3C0+(y%8)*4+(xx//8)*32+(xx%8)//2
                            shift=(xx%2)*4
                            pixel=15 if row&(1<<x) else bg
                            expected[at]=(expected[at]&~(15<<shift))|(pixel<<shift)
                    self.prepare(uc,rows,bg,fill)
                    uc.emu_start(0x08000001+SLOT[0]+odd*8,RETURN,count=3000)
                    self.assertEqual(bytes(uc.mem_read(DEST-0x100,0x500)),expected)
                    self.assertEqual(uc.reg_read(UC_ARM_REG_PC),RETURN)
                    self.registers(uc)

    def test_out_of_range_background_returns_to_original_renderer(self):
        uc=self.cpu()
        for odd in (0,1):
            for bg in (16,128,255):
                self.prepare(uc,[0x1234]*16,bg,b'\xA5'*0x500)
                target=0x08001350 if odd else 0x080011C8
                uc.emu_start(0x08000001+SLOT[0]+odd*8,target,count=200)
                self.assertEqual(uc.reg_read(UC_ARM_REG_PC),target)
                self.assertEqual(uc.reg_read(UC_ARM_REG_R0),DEST)
                self.assertEqual(uc.reg_read(UC_ARM_REG_R1),GLYPH)
                self.assertEqual(uc.reg_read(UC_ARM_REG_LR),RETURN|1)
                self.assertEqual(bytes(uc.mem_read(DEST-0x100,0x500)),b'\xA5'*0x500)
                self.registers(uc)

    def test_unrecognized_rom_is_rejected(self):
        with self.assertRaises(ValueError):build(bytes(0x800000))


if __name__=='__main__':unittest.main()

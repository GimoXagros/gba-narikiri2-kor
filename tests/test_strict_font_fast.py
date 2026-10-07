"""Synthetic CPU check covers literal rows, sparse masks and register ownership."""
import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from strict_asset_fontrows8_fast import apply,code_pair
from strict_asset_fontrows8 import DECODER,FONT_START,GROUP_BASES,LENGTHS,STREAM,MASKS,SYMBOLS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_SP,UC_ARM_REG_LR


class FastFontTests(unittest.TestCase):
    def test_dense_sparse_empty_and_escaped_rows(self):
        original=bytearray(0x800000);before,_=code_pair()
        original[DECODER:DECODER+len(before)]=before
        original[FONT_START:FONT_START+3]=bytes((0,1,2))
        struct.pack_into('<H',original,GROUP_BASES,0)
        original[LENGTHS:LENGTHS+3]=bytes((18,8,0))
        original[STREAM:STREAM+26]=bytes((255,0xCD,0xAB,*range(1,16),*range(8)))
        struct.pack_into('<3H',original,MASKS,0xFFFF,0x5555,0)
        struct.pack_into('<16H',original,SYMBOLS,*range(0x100,0x110))
        candidate=apply(original)
        expected=[struct.pack('<16H',0xABCD,*range(0x101,0x110)),
            struct.pack('<16H',*(v for i in range(8) for v in (0x100+i,0))),bytes(32)]
        for image in (original,candidate):
            uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB);uc.mem_map(0x08000000,0x800000)
            uc.mem_write(0x08000000,bytes(image));uc.mem_map(0x02000000,0x1000);uc.mem_map(0x03000000,0x8000)
            for index,wanted in enumerate(expected):
                uc.mem_write(0x02000000,b'\xA5'*40)
                saved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7)
                for r in saved:uc.reg_write(r,0x12340000+r)
                uc.reg_write(UC_ARM_REG_R0,index);uc.reg_write(UC_ARM_REG_R1,0x02000004)
                uc.reg_write(UC_ARM_REG_SP,0x03007000);uc.reg_write(UC_ARM_REG_LR,0x080A0001)
                uc.emu_start(0x08000001+DECODER,0x080A0000,count=2000)
                self.assertEqual(bytes(uc.mem_read(0x02000000,40)),b'\xA5'*4+wanted+b'\xA5'*4)
                self.assertEqual(uc.reg_read(UC_ARM_REG_SP),0x03007000)
                for r in saved:self.assertEqual(uc.reg_read(r),0x12340000+r)

    def test_unrecognised_decoder_is_not_patched(self):
        with self.assertRaises(ValueError):apply(bytes(0x800000))


if __name__=='__main__':unittest.main()

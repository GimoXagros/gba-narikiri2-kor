"""Every existing compact glyph ID keeps its original persistent token bytes."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from strict_default_names import pack_name,unpack_name,assemble_decoder,assemble_initializer
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB
from unicorn.arm_const import *


class DefaultNameTests(unittest.TestCase):
    def test_all512_ids_in_each_fixed_count_cpu_exact(self):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for at in (0x100000,0x200000,0x300000,0x400000):u.mem_map(at,0x1000)
        u.mem_write(0x100000,assemble_decoder(0x100000))
        for glyph in range(512):
            for count in (1,2,3):
                native=bytes((127,glyph//31+1,glyph%31+1))*count
                packed=pack_name(native);self.assertEqual(unpack_name(packed,count),native+b'\0')
                u.mem_write(0x200000,packed);u.mem_write(0x300000,b'\xa5'*32)
                for reg,value in ((UC_ARM_REG_R0,0x200000),(UC_ARM_REG_R1,0x300004),
                    (UC_ARM_REG_R2,count),(UC_ARM_REG_R3,19),(UC_ARM_REG_SP,0x400ff0),(UC_ARM_REG_LR,0x100801)):
                    u.reg_write(reg,value)
                u.emu_start(0x100001,0x100800,count=1000)
                self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x400ff0)
                self.assertEqual(u.reg_read(UC_ARM_REG_R0),len(native)+1)
                self.assertEqual(bytes(u.mem_read(0x300000,32)),b'\xa5'*4+native+b'\0'+b'\xa5'*(27-len(native)))

    def test_name_format_rejects_other_text_count_padding_and_glyphs(self):
        for native in (b'ABC',b'',b'\x7f\x20\x01',b'\x7f\x11\x11',b'\x7f\x01\x01'*4):
            with self.assertRaises(ValueError):pack_name(native)
        with self.assertRaises(ValueError):unpack_name(b'\xff'*4,3)
        for second,count in ((False,3),(True,2)):
            self.assertLess(len(assemble_initializer(0x08c92200,fixed_decoder=0x08c92401,
                stream_decoder=0x08c91601,count=count,second=second,fail_stop=0x08c91b01)),128)


if __name__=='__main__':unittest.main()

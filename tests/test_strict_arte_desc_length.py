"""ROM-free ABI/lifetime checks for the description byte-length adapter."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from strict_arte_desc_length import assemble, diagnostic_patch, HELPER
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import *


class ArteDescriptionLengthTest(unittest.TestCase):
    def execute_helper(self, payload, decoded=True, failed=False):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        u.mem_map(0x08000000,0x800000)
        u.mem_map(0x02000000,0x40000)
        u.mem_map(0x03000000,0x8000)
        helper,call=assemble()
        self.assertEqual(len(helper),48)
        self.assertEqual(len(call),4)
        u.mem_write(0x08000000+HELPER,helper)
        source=0x08200000 if decoded else 0x02002000
        stack,stop=0x03007E00,0x080001C0
        u.mem_write(source,payload)
        u.mem_write(stack-512,b'\xA5'*544)
        saved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
               UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
        for reg in saved:u.reg_write(reg,0x12345678)
        u.reg_write(UC_ARM_REG_R0,source)
        u.reg_write(UC_ARM_REG_SP,stack)
        u.reg_write(UC_ARM_REG_LR,stop|1)
        calls=[]
        def callback(cpu,address,size,data):
            if address==0x080B9C00:
                calls.append('owned')
                dest=cpu.reg_read(UC_ARM_REG_R1)
                self.assertEqual(dest,stack-296)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R2),288)
                if failed:cpu.reg_write(UC_ARM_REG_R0,0)
                elif decoded:
                    cpu.mem_write(dest,payload)
                    cpu.reg_write(UC_ARM_REG_R0,dest)
                    cpu.reg_write(UC_ARM_REG_R1,dest)
                    cpu.reg_write(UC_ARM_REG_R2,len(payload))
                else:
                    cpu.reg_write(UC_ARM_REG_R1,0)
                    cpu.reg_write(UC_ARM_REG_R2,0)
                cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
            elif address==0x080A6BDC:
                calls.append('strlen')
                pointer=cpu.reg_read(UC_ARM_REG_R0)
                self.assertEqual(pointer,stack-296 if decoded else source)
                self.assertEqual(bytes(cpu.mem_read(pointer,len(payload))),payload)
                cpu.reg_write(UC_ARM_REG_R0,payload.index(b'\0'))
                cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,callback)
        u.emu_start((0x08000000+HELPER)|1,0x080B9DE4 if failed else stop,count=1000)
        self.assertEqual(bytes(u.mem_read(stack,32)),b'\xA5'*32)
        if failed:
            self.assertEqual(u.reg_read(UC_ARM_REG_PC),0x080B9DE4)
            self.assertEqual(calls,['owned'])
        else:
            self.assertEqual(calls,['owned','strlen'])
            self.assertEqual(u.reg_read(UC_ARM_REG_R0),payload.index(b'\0'))
            self.assertEqual(u.reg_read(UC_ARM_REG_PC),stop)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),stack)
            for reg in saved:self.assertEqual(u.reg_read(reg),0x12345678)

    def test_native_length_and_owned_buffer_lifetime(self):
        for payload in (b'\0',b'x'*34+b'\0',b'x'*40+b'\0',
                        b'x'*282+b'\0',b'ab\0not_part_of_strlen\0'):
            for decoded in (False,True):
                with self.subTest(size=len(payload),decoded=decoded):
                    self.execute_helper(payload,decoded)

    def test_decode_failure_does_not_call_native_strlen(self):
        self.execute_helper(b'x\0',failed=True)

    def test_unbound_source_cannot_be_patched(self):
        with self.assertRaisesRegex(ValueError,'Exact 8 MiB Japanese'):
            diagnostic_patch(bytes(0x800000),bytes(0x800000))


if __name__=='__main__':unittest.main()

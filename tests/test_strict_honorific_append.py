"""ROM-free wrapper lifetime, return ABI, and rejected decode checks."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import strict_honorific_append
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import *


class HonorificAppendTest(unittest.TestCase):
    component=strict_honorific_append
    consumer=0x080A6AEC
    def run_case(self,decoded,payload,failed=False):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for at,n in [(0x08000000,0x800000),(0x02000000,0x40000),(0x03000000,0x8000)]:u.mem_map(at,n)
        helper,calls=self.component.assemble();self.assertEqual(len(calls),2)
        u.mem_write(0x08000000+self.component.HELPER,helper)
        dest,source,stack,stop=0x02001000,0x082BF490,0x03007C00,0x080001C0
        u.mem_write(source,payload);u.mem_write(dest-16,b'\xA5'*400);u.mem_write(dest,b'NAME\0')
        u.mem_write(stack-320,b'\xB6'*352)
        saved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
               UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
        for i,r in enumerate(saved):u.reg_write(r,0x10101010+i)
        for r,v in [(UC_ARM_REG_R0,dest),(UC_ARM_REG_R1,source),(UC_ARM_REG_SP,stack),(UC_ARM_REG_LR,stop|1)]:u.reg_write(r,v)
        events=[]
        def hook(cpu,address,size,data):
            if address==0x080B9C00:
                events.append('decode');tmp=cpu.reg_read(UC_ARM_REG_R1)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R0),source)
                self.assertEqual(tmp,stack-296);self.assertEqual(cpu.reg_read(UC_ARM_REG_R2),288)
                if failed:
                    for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2):cpu.reg_write(r,0)
                elif decoded:
                    cpu.mem_write(tmp,payload);cpu.reg_write(UC_ARM_REG_R0,tmp)
                else:cpu.reg_write(UC_ARM_REG_R0,source)
                cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
            elif address==self.consumer:
                events.append('cat');src=cpu.reg_read(UC_ARM_REG_R1)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R0),dest)
                self.assertEqual(src,stack-296 if decoded else source)
                self.assertEqual(bytes(cpu.mem_read(src,len(payload))),payload)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_SP),stack-296)
                cpu.mem_write(dest+4,payload)
                cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,hook)
        u.emu_start((0x08000000+self.component.HELPER)|1,0x080B9DE4 if failed else stop,count=1000)
        self.assertEqual(events,['decode'] if failed else ['decode','cat'])
        self.assertEqual(bytes(u.mem_read(dest-16,16)),b'\xA5'*16)
        self.assertEqual(bytes(u.mem_read(stack-320,24)),b'\xB6'*24)
        self.assertEqual(bytes(u.mem_read(stack,32)),b'\xB6'*32)
        if failed:
            self.assertEqual(bytes(u.mem_read(dest,5)),b'NAME\0')
            self.assertEqual(u.reg_read(UC_ARM_REG_PC),0x080B9DE4)
        else:
            self.assertEqual(bytes(u.mem_read(dest,4+len(payload))),b'NAME'+payload)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),stack)
            self.assertEqual(u.reg_read(UC_ARM_REG_R0),dest)
            for i,r in enumerate(saved):self.assertEqual(u.reg_read(r),0x10101010+i)
    def test_native_and_decoded_lifetime(self):
        for decoded in (False,True):
            for payload in (b'\0',b'\x8f\xa0\0',b'\x91\x95\x90\xc3\0',b'a'*287+b'\0'):
                with self.subTest(decoded=decoded,size=len(payload)):self.run_case(decoded,payload)
    def test_failed_decode_never_appends(self):self.run_case(True,b'\x8f\xa0\0',True)
    def test_wrong_source_rejected(self):
        with self.assertRaises(ValueError):self.component.diagnostic_patch(bytes(0x800000),bytes(0x800000))


if __name__=='__main__':unittest.main()

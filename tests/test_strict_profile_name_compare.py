"""Native comparison operand order, signed result, lifetime and ABI contracts."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from strict_profile_name_compare import HELPER,assemble,diagnostic_patch
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import *


class ProfileNameCompareTest(unittest.TestCase):
    def run_case(self,decoded,result,failed=False):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for a,n in [(0x08000000,0x800000),(0x02000000,0x40000),(0x03000000,0x8000)]:u.mem_map(a,n)
        helper,call=assemble();self.assertEqual(len(call),4)
        u.mem_write(0x08000000+HELPER,helper)
        source,profile,stack,stop=0x082BF29C,0x02001013,0x03007C00,0x080001C0
        payload=b'\x92\xdd\x8c\x49\x8e\xfe\0'
        u.mem_write(source,payload);u.mem_write(profile-16,b'\xa5'*64);u.mem_write(profile,payload)
        before=bytes(u.mem_read(profile-16,64));u.mem_write(stack-320,b'\xb6'*352)
        saved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
               UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
        for i,r in enumerate(saved):u.reg_write(r,0x10101010+i)
        for r,v in [(UC_ARM_REG_R0,source),(UC_ARM_REG_R1,profile),(UC_ARM_REG_SP,stack),(UC_ARM_REG_LR,stop|1)]:u.reg_write(r,v)
        events=[]
        def hook(cpu,address,size,data):
            if address==0x080B9C00:
                events.append('decode');tmp=cpu.reg_read(UC_ARM_REG_R1)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R0),source)
                self.assertEqual(tmp,stack-296);self.assertEqual(cpu.reg_read(UC_ARM_REG_R2),288)
                if failed:cpu.reg_write(UC_ARM_REG_R0,0)
                elif decoded:cpu.mem_write(tmp,payload);cpu.reg_write(UC_ARM_REG_R0,tmp)
                else:cpu.reg_write(UC_ARM_REG_R0,source)
                cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
            elif address==0x080A6B34:
                events.append('compare')
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R0),stack-296 if decoded else source)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R1),profile)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_SP),stack-296)
                cpu.reg_write(UC_ARM_REG_R0,result&0xffffffff)
                cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,hook)
        u.emu_start((0x08000000+HELPER)|1,0x080B9DE4 if failed else stop,count=1000)
        self.assertEqual(events,['decode'] if failed else ['decode','compare'])
        self.assertEqual(bytes(u.mem_read(profile-16,64)),before)
        self.assertEqual(bytes(u.mem_read(stack-320,24)),b'\xb6'*24)
        self.assertEqual(bytes(u.mem_read(stack,32)),b'\xb6'*32)
        if failed:self.assertEqual(u.reg_read(UC_ARM_REG_PC),0x080B9DE4)
        else:
            self.assertEqual(u.reg_read(UC_ARM_REG_R0),result&0xffffffff)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),stack)
            for i,r in enumerate(saved):self.assertEqual(u.reg_read(r),0x10101010+i)
    def test_native_and_decoded_operand_order_and_signed_return(self):
        for decoded in (False,True):
            for result in (-255,-1,0,1,255):
                with self.subTest(decoded=decoded,result=result):self.run_case(decoded,result)
    def test_failed_decode_never_compares(self):self.run_case(True,0,True)
    def test_wrong_source_rejected(self):
        with self.assertRaises(ValueError):diagnostic_patch(bytes(0x800000),bytes(0x800000))


if __name__=='__main__':unittest.main()

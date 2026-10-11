"""ROM-free CPU checks for bounded persistent name fields and native inputs."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from strict_profile_name_copy import HELPER, assemble, diagnostic_patch
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import *


class ProfileNameCopyTest(unittest.TestCase):
    def run_case(self,capacity,payload,decoded=True,failed=False):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for start,size in [(0x08000000,0x800000),(0x02000000,0x40000),(0x03000000,0x8000)]:u.mem_map(start,size)
        helper,calls=assemble();self.assertEqual(len(calls),2)
        u.mem_write(0x08000000+HELPER,helper)
        dest,source,stack,stop=0x02000113,0x02010000,0x03007E00,0x080001C0
        u.mem_write(dest-16,b'\xA5'*(capacity+32));u.mem_write(source,payload)
        u.mem_write(stack-64,b'\xB6'*96)
        saved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
               UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
        for i,r in enumerate(saved):u.reg_write(r,0x10101010+i)
        for r,v in [(UC_ARM_REG_R0,dest),(UC_ARM_REG_R1,source),(UC_ARM_REG_SP,stack),(UC_ARM_REG_LR,stop|1)]:u.reg_write(r,v)
        count=[]
        def hook(cpu,address,size,data):
            if address!=0x080B9C00:return
            count.append(address)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R0),source)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R1),dest)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R2),capacity)
            if failed or (decoded and len(payload)>capacity):
                for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2):cpu.reg_write(r,0)
            elif decoded:
                cpu.mem_write(dest,payload)
                cpu.reg_write(UC_ARM_REG_R0,dest);cpu.reg_write(UC_ARM_REG_R1,dest);cpu.reg_write(UC_ARM_REG_R2,len(payload))
            else:
                cpu.reg_write(UC_ARM_REG_R0,source);cpu.reg_write(UC_ARM_REG_R1,0);cpu.reg_write(UC_ARM_REG_R2,0)
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,hook)
        failure=failed or payload.find(b'\0')>=capacity or b'\0' not in payload
        u.emu_start((0x08000000+HELPER+(4 if capacity==13 else 0))|1,0x080B9DE4 if failure else stop,count=5000)
        self.assertEqual(len(count),1)
        self.assertEqual(bytes(u.mem_read(dest-16,16)),b'\xA5'*16)
        self.assertEqual(bytes(u.mem_read(dest+capacity,16)),b'\xA5'*16)
        self.assertEqual(bytes(u.mem_read(stack,32)),b'\xB6'*32)
        if failure:self.assertEqual(u.reg_read(UC_ARM_REG_PC),0x080B9DE4)
        else:
            actual=payload[:payload.index(0)+1]
            self.assertEqual(bytes(u.mem_read(dest,len(actual))),actual)
            self.assertEqual(u.reg_read(UC_ARM_REG_R0),dest)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),stack)
            for i,r in enumerate(saved):self.assertEqual(u.reg_read(r),0x10101010+i)
    def test_both_persistent_fields_and_native_passthrough(self):
        for cap in (19,13):
            for payload in (b'\0',b'\x7f\x0e\x06\x7f\x04\x19\x7f\x09\x0b\0',b'a'*(cap-1)+b'\0'):
                for decoded in (False,True):
                    with self.subTest(cap=cap,size=len(payload),decoded=decoded):self.run_case(cap,payload,decoded)
    def test_boundary_rejection_does_not_touch_next_field(self):
        for cap in (19,13):
            for decoded in (False,True):self.run_case(cap,b'a'*cap+b'\0',decoded)
    def test_decode_failure_never_returns_a_profile(self):
        self.run_case(19,b'ab\0',failed=True)
    def test_wrong_source_rejected(self):
        with self.assertRaises(ValueError):diagnostic_patch(bytes(0x800000),bytes(0x800000))


if __name__=='__main__':unittest.main()

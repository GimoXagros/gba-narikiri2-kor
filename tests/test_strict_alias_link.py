"""Shared v2 adapter with all SELECT_JOB synthetic variants and accessor ABI."""
import struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
from strict_alias_link import assemble_job,assemble_arte_accessor
from strict_packed_tree import pack_tree
import test_strict_runtime_select_job as job_fixture
from test_strict_packed_tree import PackedThumbDecoder
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_MEM_READ
from unicorn.arm_const import *

class LinkedSelectJob(job_fixture.SyntheticSelectJobCPU):
    @classmethod
    def setUpClass(cls):
        cls.image,cls.desc,book,cls.expected=job_fixture.fixture();cls.book=pack_tree(book)
        code,entry=assemble_job(job_fixture.CODE,descriptors=job_fixture.DESC,book=job_fixture.BOOK,book_bytes=len(cls.book),unit_decoder=job_fixture.CODE+0x801)
        cls.code=code+b'\0'*(0x800-len(code))+PackedThumbDecoder().code

class LinkedArteAccessor(unittest.TestCase):
    def test_every_record_mode_preserves_context_and_registers(self):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.mem_map(0x08000000,0x800000);u.mem_map(0x03000000,0x8000)
        u.mem_write(0x080b8000,assemble_arte_accessor(0x080b8000,fail_stop=0x080b9801))
        for i in range(232):
            u.mem_write(0x08374a38+20*i,struct.pack('<II',0x082bcfe0 if i in (158,159) else 0x08200000+4*i,0x08201000+4*i))
        for i in list(range(232))+[159,158,158,159]:
            for mode in (0,1,2,0xffffffff):
                u.reg_write(UC_ARM_REG_R0,i);u.reg_write(UC_ARM_REG_R1,mode)
                for r in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):u.reg_write(r,0x12345678)
                u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x080bff01)
                u.emu_start(0x080b8001,0x080bff00,count=1000)
                expected=0x08201000+4*i if mode else {158:0x0a2bcfe0,159:0x0c2bcfe0}.get(i,0x08200000+4*i)
                self.assertEqual(u.reg_read(UC_ARM_REG_R0),expected)
                self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x03007e00)
                self.assertEqual(u.reg_read(UC_ARM_REG_PC),0x080bff00)
                for r in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):self.assertEqual(u.reg_read(r),0x12345678)
        u.mem_write(0x08374a38+20*158,struct.pack('<I',0x08201234))
        u.reg_write(UC_ARM_REG_R0,158);u.reg_write(UC_ARM_REG_R1,0);u.reg_write(UC_ARM_REG_SP,0x03007e00)
        u.emu_start(0x080b8001,0x080b9800,count=1000)
        self.assertEqual(u.reg_read(UC_ARM_REG_PC),0x080b9800)

    def test_invalid_indices_fail_before_record_memory_read(self):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.mem_map(0x08000000,0x800000);u.mem_map(0x03000000,0x8000)
        code=assemble_arte_accessor(0x080b8000,fail_stop=0x080b9801)
        self.assertEqual(len(code),88)
        u.mem_write(0x080b8000,code)
        reads=[]
        def record(_u,_access,address,size,_value,_data):
            if not (0x080b8000<=address<0x080b8000+len(code)):
                reads.append((address,size))
        u.hook_add(UC_HOOK_MEM_READ,record)
        for index in (232,233,255,65535,0x80000000,0xffffffff):
            for mode in (0,1):
                reads.clear();u.reg_write(UC_ARM_REG_R0,index);u.reg_write(UC_ARM_REG_R1,mode)
                u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x080bff01)
                u.emu_start(0x080b8001,0x080b9800,count=100)
                self.assertEqual(u.reg_read(UC_ARM_REG_PC),0x080b9800)
                self.assertEqual(reads,[])

if __name__=='__main__':unittest.main()

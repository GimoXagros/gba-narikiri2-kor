"""Native popup centering grid, field bounds and adapter-owned stack ABI."""
import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_halfspace_prototype import ROOT,assemble
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import *

NORMAL=b'\x88\x9f';HALF=b'\x80\x40';FULL=b'\x81\x40'


class PopupCenterTests(unittest.TestCase):
    def copy(self,source):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        u.mem_map(0x08000000,0x100000);u.mem_map(0x02000000,0x40000)
        code=assemble((ROOT/'asm/halfspace_popup_center.s').read_text(),0x25d08)
        self.assertLessEqual(len(code),160);u.mem_write(0x08025d08,code)
        dest=0x02001020;src=0x02002000;sp=0x0203f000;stop=0x08000200
        u.mem_write(dest-32,b'\xa5'*96);u.mem_write(src,source+b'\0')
        saved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6)
        u.mem_write(sp,struct.pack('<4I',*[0x12340000+r for r in saved],stop|1))
        for r,v in ((UC_ARM_REG_R4,dest),(UC_ARM_REG_R6,src),(UC_ARM_REG_R3,0),(UC_ARM_REG_SP,sp)):u.reg_write(r,v)
        for r in (UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):u.reg_write(r,0x12340000+r)
        def strcpy(cpu,at,size,_):
            if at!=0x080a6b90:return
            data=bytes(cpu.mem_read(cpu.reg_read(UC_ARM_REG_R1),512));data=data[:data.index(0)+1]
            cpu.mem_write(cpu.reg_read(UC_ARM_REG_R0),data)
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,strcpy);u.emu_start(0x08025d09,stop,count=10000)
        self.assertEqual(u.reg_read(UC_ARM_REG_PC),stop);self.assertEqual(u.reg_read(UC_ARM_REG_R0),stop|1)
        self.assertEqual(u.reg_read(UC_ARM_REG_SP),sp+16)
        for r in saved+(UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):self.assertEqual(u.reg_read(r),0x12340000+r)
        self.assertEqual(bytes(u.mem_read(dest-32,32)),b'\xa5'*32);self.assertEqual(bytes(u.mem_read(dest+32,32)),b'\xa5'*32)
        data=bytes(u.mem_read(dest,32));return data[:data.index(0)]

    def test_empty_odd_even_and_mode_prefix_keep_native_rounding(self):
        for n in range(11):
            for prefix in (b'',b'\x12'):
                raw=prefix+NORMAL*n
                self.assertEqual(self.copy(raw),FULL*(9-(n+1)//2)+raw)

    def test_halfwidth_names_center_on_six_pixel_grid_with_left_ties(self):
        for n in range(1,11):
            for spaces in range(1,n+1):
                raw=NORMAL*(n-spaces)+HALF*spaces;h=2*n-spaces;pad=(36-h)//2
                expected=FULL*(pad//2)+(HALF if pad&1 else b'')+raw
                if len(expected)>31:expected=raw
                result=self.copy(raw);self.assertEqual(result,expected)
                if len(expected)!=len(raw):self.assertIn(pad*6+h*3-108,(-3,0))

    def test_field_capacity_drops_padding_or_rejects_long_source(self):
        self.assertEqual(self.copy(HALF*15),HALF*15)
        self.assertEqual(self.copy(NORMAL*16),b'')
        self.assertEqual(self.copy(b'\x12'+HALF*15),b'\x12'+HALF*15)


if __name__=='__main__':unittest.main()

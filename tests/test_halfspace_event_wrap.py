"""Page clock, physical width, closing punctuation and buffer/ABI boundaries."""
import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_halfspace_prototype import assemble,ROOT
from unicorn import *
from unicorn.arm_const import *

ENTRY=0x08001350;BUF=0x02001000;LENGTH=0x02002000;CLOCK=LENGTH+4
NORMAL=b'\x88\x9f';HALF=b'\x80\x40';FULL=b'\x81\x40';PUNCT=b'\x81\x49'

class EventWrapTests(unittest.TestCase):
    def run_case(self,payload,clock):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for at,n in ((0x08000000,0x100000),(0x02000000,0x40000)):u.mem_map(at,n)
        code=assemble((ROOT/'asm/halfspace_event_wrap.s').read_text(),ENTRY-0x08000000)
        self.assertLessEqual(len(code),0x14e0-0x1350)
        u.mem_write(ENTRY,code);u.mem_write(BUF,b'\xa5'*192)
        u.mem_write(BUF,payload);u.mem_write(LENGTH,struct.pack('<II',len(payload),clock))
        saved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
        values={r:0x12340000+r for r in saved};values.update({UC_ARM_REG_R4:BUF,UC_ARM_REG_R5:LENGTH,UC_ARM_REG_R7:CLOCK})
        for r,v in values.items():u.reg_write(r,v)
        for r,v in ((UC_ARM_REG_R0,clock),(UC_ARM_REG_SP,0x0203f000),(UC_ARM_REG_LR,0x08000201)):u.reg_write(r,v)
        def kinsoku(cpu,at,size,_):
            if at==0x0809a968:
                cpu.reg_write(UC_ARM_REG_R0,int(bytes(cpu.mem_read(cpu.reg_read(UC_ARM_REG_R0),2))==PUNCT))
                cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,kinsoku)
        u.emu_start(ENTRY|1,0x08000200,count=10000)
        self.assertEqual(u.reg_read(UC_ARM_REG_PC),0x08000200)
        self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x0203f000)
        for r,v in values.items():self.assertEqual(u.reg_read(r),v)
        n,c=struct.unpack('<II',bytes(u.mem_read(LENGTH,8)))
        self.assertEqual(bytes(u.mem_read(BUF+160,32)),b'\xa5'*32)
        return bytes(u.mem_read(BUF,n)),c

    def test_original_full_cell_clock_and_break(self):
        out,clock=self.run_case(NORMAL*18,36)
        self.assertEqual(out,NORMAL*17+b'\n'+NORMAL);self.assertEqual(clock,38)

    def test_narrow_spaces_do_not_delay_page_clock(self):
        out,clock=self.run_case(HALF*18,36)
        self.assertEqual(out,HALF*18);self.assertEqual(clock,38)
        out,clock=self.run_case(NORMAL*12+HALF*12,50)
        self.assertEqual(out,NORMAL*12+HALF*11+b'\n'+HALF);self.assertEqual(clock,50)

    def test_odd_width_closing_run_moves_with_preceding_glyph(self):
        for n in (1,2,3):
            out,clock=self.run_case(NORMAL*16+HALF+NORMAL+PUNCT*n,38+2*n)
            self.assertEqual(out,NORMAL*16+HALF+b'\n'+NORMAL+PUNCT*n)
            self.assertEqual(clock,38+2*n)

    def test_manual_line_and_page_boundary_are_untouched(self):
        for payload,clock in ((NORMAL*17+b'\n',36),(NORMAL+b'\n'+HALF*20,48),(NORMAL*36,72),(NORMAL*17,34)):
            self.assertEqual(self.run_case(payload,clock),(payload,clock))

    def test_full_space_and_invalid_length(self):
        self.assertEqual(self.run_case(NORMAL*17+FULL,36),(NORMAL*17+b'\n'+FULL,38))
        payload=NORMAL*80
        self.assertEqual(self.run_case(payload,36),(payload,36))

    def test_physical_scan_continues_after_manual_or_inserted_line(self):
        for prefix in (NORMAL+b'\n',NORMAL*17+b'\n'):
            payload=prefix+NORMAL*18
            out,clock=self.run_case(payload,70)
            self.assertEqual(out,prefix+NORMAL*17+b'\n'+NORMAL)
            self.assertEqual(clock,70)

    def test_incomplete_variable_pair_at_odd_clock_is_never_reflowed(self):
        partial=NORMAL*17+HALF+NORMAL[:1]
        for clock in range(37,72,2):self.assertEqual(self.run_case(partial,clock),(partial,clock))
        self.assertEqual(self.run_case(partial+NORMAL[1:],38),(NORMAL*17+HALF+b'\n'+NORMAL,38))

    def test_mixed_native_tokens_defer_to_full_printer_without_guessing_pairs(self):
        for token in (b'A',b'\xa4\xa5',b'\x12',b'\x10'):
            payload=NORMAL*16+token+NORMAL*4
            self.assertEqual(self.run_case(payload,50),(payload,50))

if __name__=='__main__':unittest.main()

"""Long/native/variable inputs cannot overflow the allocated event output."""
import sys,struct,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from strict_event_allocation import assemble
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import *

class EventAllocationTests(unittest.TestCase):
    def run_size(self,source,first=b'FIRST',second=b'SECOND',failed=False):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.mem_map(0x08000000,0x800000);u.mem_map(0x02000000,0x40000);u.mem_map(0x03000000,0x8000)
        u.mem_write(0x080b8000,assemble(0x080b8000,fail_stop=0x080b9801));u.mem_write(0x08003520,b'\x70\x47')
        u.mem_write(0x02001000,source+b'\0');u.mem_write(0x02002000,first+b'\0');u.mem_write(0x02002100,second+b'\0')
        u.mem_write(0x03007e00,struct.pack('<I',0x02002000))
        registers={UC_ARM_REG_R4:111,UC_ARM_REG_R5:0x02001000,UC_ARM_REG_R6:333,UC_ARM_REG_R7:444,UC_ARM_REG_R8:555,UC_ARM_REG_R9:666,UC_ARM_REG_R10:0x02002100,UC_ARM_REG_R11:777}
        for r,v in registers.items():u.reg_write(r,v)
        u.reg_write(UC_ARM_REG_SP,0x03007e00);u.reg_write(UC_ARM_REG_LR,0x080bff01)
        sizes=[]
        def hook(uc,at,size,data):
            if at==0x08003520:sizes.append(uc.reg_read(UC_ARM_REG_R0));uc.reg_write(UC_ARM_REG_R0,0x02003000)
        u.hook_add(UC_HOOK_CODE,hook)
        stop=0x080b9800 if failed else 0x080bff00
        u.emu_start(0x080b8001,stop,count=20000);self.assertEqual(u.reg_read(UC_ARM_REG_PC),stop)
        if failed:self.assertEqual(sizes,[]);return
        for r,v in registers.items():self.assertEqual(u.reg_read(r),v)
        self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x03007e00)
        return sizes
    def test_exact_native_and_substituted_lengths_including_longest(self):
        for text in (b'',b'A'*144,b'B'*282,b'@B @G',b'@B'*141,b'@X@B@G@'):
            first=b'123456789012';second=b'ABC'
            expected=text.replace(b'@B',first).replace(b'@G',second)+b'\0'
            self.assertEqual(self.run_size(text,first,second),[len(expected)])
        self.assertEqual(self.run_size(b'@B@G',b'',b''),[1])
    def test_unterminated_input_and_invalid_persistent_name_bounds(self):
        self.run_size(b'A'*283,failed=True)
        self.run_size(b'@B',b'A'*13,failed=True)
        self.run_size(b'@G',second=b'B'*13,failed=True)

if __name__=='__main__':unittest.main()

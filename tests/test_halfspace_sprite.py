"""Text descriptor identity determines width without touching affine metadata."""
import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_halfspace_prototype import ROOT,assemble
from unicorn import *
from unicorn.arm_const import *

ENTRY=0x080013ec;OBJ=0x02001000;SOURCE=0x02002000;STOP=0x08000200
ALIAS=0x080cab04

class SpriteSpacingTests(unittest.TestCase):
    def cpu(self):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        u.mem_map(0x08000000,0x100000);u.mem_map(0x02000000,0x40000)
        code=assemble((ROOT/'asm/halfspace_sprite.s').read_text().replace('SPRITE_DESCRIPTOR',str(ALIAS))+'\n'+(ROOT/'asm/halfspace_sprite_font.s').read_text()+'\nentry_table: .word sprite_created,sprite_advance,sprite_font',ENTRY-0x08000000)
        entries=struct.unpack('<3I',code[-12:]);u.mem_write(ENTRY,code[:-12])
        for r in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):u.reg_write(r,0x12340000+r)
        u.reg_write(UC_ARM_REG_SP,0x0203f000);u.reg_write(UC_ARM_REG_LR,STOP|1)
        return u,entries

    def test_creator_uses_descriptor_type_without_touching_matrix_index(self):
        for token,width in ((b'\x80\x40',6),(b'\x81\x40',0),(b'\x88\x9f',0)):
            u,e=self.cpu();before=bytearray(b'\xa5'*32);u.mem_write(OBJ,bytes(before));u.mem_write(SOURCE,token)
            u.reg_write(UC_ARM_REG_R0,OBJ);u.reg_write(UC_ARM_REG_R8,SOURCE)
            u.emu_start(e[0]|1,STOP,count=100)
            expected=before;expected[22]=2
            if width:struct.pack_into('<I',expected,4,ALIAS)
            self.assertEqual(bytes(u.mem_read(OBJ,32)),expected)
            self.assertEqual(u.reg_read(UC_ARM_REG_R1),2)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x0203f000)

    def test_advance_wraps_coordinates_and_leaves_y_and_array_pointer(self):
        for callback in (0,ALIAS,0x08374670,0x08001349):
            for x in (0,12,210,65530):
                u,e=self.cpu();u.mem_write(OBJ+4,struct.pack('<I',callback));u.mem_write(OBJ+23,b'\x06');u.reg_write(UC_ARM_REG_R0,OBJ);u.reg_write(UC_ARM_REG_R1,x)
                u.reg_write(UC_ARM_REG_R2,77);u.reg_write(UC_ARM_REG_R3,0x02003000)
                u.emu_start(e[1]|1,STOP,count=100)
                self.assertEqual(u.reg_read(UC_ARM_REG_R1),(x+(6 if callback==ALIAS else 12))&65535)
                self.assertEqual(u.reg_read(UC_ARM_REG_R2),77);self.assertEqual(u.reg_read(UC_ARM_REG_R3),0x02003000)

    def test_font_guard_only_maps_reserved_index_before_original_decoder(self):
        for index in (0,671,3839,0xffffff40):
            u,e=self.cpu();u.reg_write(UC_ARM_REG_R0,index);u.reg_write(UC_ARM_REG_R1,0x02003000)
            u.emu_start(e[2]|1,0x080b9490,count=100)
            self.assertEqual(u.reg_read(UC_ARM_REG_R0),0 if index==0xffffff40 else index)
            self.assertEqual(u.reg_read(UC_ARM_REG_R1),0x02003000)
            self.assertEqual(u.reg_read(UC_ARM_REG_LR),STOP|1)

    def test_leaf_position_hook_restores_native_return_address(self):
        # The native positioner is a leaf: BL must not replace its caller LR.
        u,e=self.cpu();site=0x25208
        u.mem_write(0x08000000+site,assemble(f'push {{lr}}\nbl {e[1]}\npop {{r0}}\nmov lr,r0\nbx lr',site))
        u.mem_write(OBJ+4,struct.pack('<I',ALIAS));u.reg_write(UC_ARM_REG_R0,OBJ)
        u.reg_write(UC_ARM_REG_R1,12)
        u.emu_start(0x08000001+site,STOP,count=100)
        self.assertEqual(u.reg_read(UC_ARM_REG_PC),STOP)
        self.assertEqual(u.reg_read(UC_ARM_REG_R1),18)
        self.assertEqual(u.reg_read(UC_ARM_REG_LR),STOP|1)
        self.assertEqual(u.reg_read(UC_ARM_REG_SP),0x0203f000)

if __name__=='__main__':unittest.main()

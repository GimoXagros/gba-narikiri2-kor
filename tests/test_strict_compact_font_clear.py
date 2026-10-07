"""Exercise the complete getter boundary; the cache consumes local bytes."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from strict_compact_font_clear import assemble, validate_banks
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import *


class ClearFontTests(unittest.TestCase):
    def test_all_512_getter_indices_both_palettes_and_invalid_glyph(self):
        clear = bytes((0, 15, 240, 255)[(i * 13 + i // 17) % 4] for i in range(16384))
        solid = bytes(b | 0xbb for b in clear)
        validate_banks(clear, solid)
        u = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        u.mem_map(0x100000, 0x1000)
        u.mem_map(0x200000, 0x4000)
        u.mem_map(0x03000000, 0x8000)
        u.mem_write(0x100000, assemble(0x100000, decoder=0x100801,
                                      cache=0x100901, clear_font=0x200000))
        u.mem_write(0x100800, b'\x70\x47')
        u.mem_write(0x100900, b'\x70\x47')
        u.mem_write(0x200000, clear)
        calls = []
        index = 0
        def hook(uc, address, size, data):
            if address == 0x100800:
                uc.reg_write(UC_ARM_REG_R0, index)
            elif address == 0x100900:
                pointer = uc.reg_read(UC_ARM_REG_R0)
                calls.append((pointer, bytes(uc.mem_read(pointer, 32))))
                uc.reg_write(UC_ARM_REG_R0, 378)
        u.hook_add(UC_HOOK_CODE, hook)
        for index, palette in [(i, p) for i in range(512) for p in (0, 11)] + [(0xffffffff, 0)]:
            calls.clear()
            u.mem_write(0x0300145a, bytes([palette]))
            u.mem_write(0x03007e00, b'\xa5' * 256)
            for reg in (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4,
                        UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                        UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11):
                u.reg_write(reg, 0x13579bdf)
            u.reg_write(UC_ARM_REG_SP, 0x03007f00)
            u.reg_write(UC_ARM_REG_LR, 0x100a01)
            u.emu_start(0x100001, 0x100a00, count=500)
            self.assertEqual(u.reg_read(UC_ARM_REG_SP), 0x03007f00)
            self.assertEqual(bytes(u.mem_read(0x03007e00, 200)), b'\xa5' * 200)
            for reg in (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4,
                        UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                        UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11):
                self.assertEqual(u.reg_read(reg), 0x13579bdf)
            if index == 0xffffffff:
                self.assertEqual(calls, [])
                self.assertEqual(u.reg_read(UC_ARM_REG_R0), 0xffffffff)
            else:
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][1], (solid if palette == 11 else clear)[index*32:(index+1)*32])
                self.assertEqual(calls[0][0], 0x03007ec8 if palette == 11 else 0x200000 + index*32)
                self.assertEqual(u.reg_read(UC_ARM_REG_R0), 378)

    def test_unrepresentable_banks_rejected(self):
        for clear, solid in ((b'\0'*32, b'\xbb'*32),
                             (b'\x10'*16384, b'\xbb'*16384),
                             (b'\0'*16384, b'\xff'*16384)):
            with self.assertRaises(ValueError):
                validate_banks(clear, solid)


if __name__ == '__main__':
    unittest.main()

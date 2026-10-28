import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_baked_no_c import helper_and_hook, native_yesno_text, HOOK
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB
from unicorn import arm_const
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR


class NoPlacementTests(unittest.TestCase):
    def test_graphic_rejects_foreign_pixels_even_under_optimized_python(self):
        for raw in (b'', bytes(256)):
            with self.assertRaises(ValueError):
                native_yesno_text(raw)

    def test_only_no_group_moves_and_registers_return_unchanged(self):
        address = 0x3AD810
        helper, hook = helper_and_hook(address)
        for option in (0, 1):
            for position in (80, 0xFFFFFFF0):
                cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
                cpu.mem_map(0x08000000, 0x800000)
                cpu.mem_map(0x02000000, 0x10000)
                cpu.mem_map(0x03000000, 0x8000)
                cpu.mem_write(0x08000000 + HOOK, hook)
                cpu.mem_write(0x08000000 + address, helper)
                values = {UC_ARM_REG_R0: 0x02000100, UC_ARM_REG_R1: 0x02000200, UC_ARM_REG_R2: position,
                          UC_ARM_REG_R3: option, UC_ARM_REG_SP: 0x03007F00, UC_ARM_REG_LR: 0x08001235}
                values.update({getattr(arm_const, f'UC_ARM_REG_R{i}'): 0x12340000 + i for i in range(4, 13)})
                for register, value in values.items():
                    cpu.reg_write(register, value)
                cpu.emu_start(0x08000000 + HOOK + 1, 0x08000000 + HOOK + 4, count=30)
                expected = ((position + (4 if option == 1 else 0)) & 0xFFFF).to_bytes(2, 'little')
                self.assertEqual(cpu.mem_read(0x0200010C, 2), expected)
                self.assertEqual(cpu.mem_read(0x0200020C, 2), expected)
                for register, value in values.items():
                    if register != UC_ARM_REG_LR:
                        self.assertEqual(cpu.reg_read(register), value)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_LR), 0x08000000 + HOOK + 5)


if __name__ == '__main__':
    unittest.main()

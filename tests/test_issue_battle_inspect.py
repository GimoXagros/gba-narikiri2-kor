"""Check the inspection wrapper on Thumb with small decoder/renderer stubs."""

from pathlib import Path
import sys
import unittest

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_THUMB, Uc
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
    UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4, UC_ARM_REG_SP,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from issue_battle_inspect import BUFFER_BYTES, ENTRY, RENDERER, assemble


class BattleInspectionTests(unittest.TestCase):
    def execute_wrapper(self, kind):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        entry = 0x08000000 + ENTRY
        decoder = 0x080B9C00
        source = 0x02001000
        stop = 0x02008000
        stack = 0x02007E00
        native = b"HP   286/  320\x00"
        decoded = bytes.fromhex("7f02197f0b137f0f05207f04197f0b137f040400")
        cpu.mem_map(entry & ~0xFFF, 0x2000)
        for address in (decoder, RENDERER & ~0xFFF):
            cpu.mem_map(address, 0x1000)
        cpu.mem_map(0x02000000, 0x10000)
        cpu.mem_write(entry, assemble())
        for address in (decoder, RENDERER):
            cpu.mem_write(address, bytes.fromhex("7047"))  # BX LR
        cpu.mem_write(source, native)
        cpu.mem_write(stack, b"\xa5" * 24)
        cpu.reg_write(UC_ARM_REG_CPSR, 0x3f)
        for reg, value in (
            (UC_ARM_REG_R0, 1), (UC_ARM_REG_R1, 3), (UC_ARM_REG_R2, source),
            (UC_ARM_REG_R4, 0x11223344), (UC_ARM_REG_SP, stack),
            (UC_ARM_REG_LR, stop | 1),
        ):
            cpu.reg_write(reg, value)

        calls = []

        def observe(current, address, size, user):
            regs = [current.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            if address == decoder:
                calls.append(address)
                self.assertEqual(regs, [source, stack - 16 - BUFFER_BYTES, BUFFER_BYTES])
                if kind == "owned":
                    current.mem_write(regs[1], decoded)
                    current.reg_write(UC_ARM_REG_R0, regs[1])
                elif kind == "invalid":
                    current.reg_write(UC_ARM_REG_R0, 0)
            elif address == RENDERER:
                calls.append(address)
                self.assertEqual(regs[:2], [1, 3])
                self.assertEqual(regs[2], stack - 16 - BUFFER_BYTES if kind == "owned" else source)
                expected = decoded if kind == "owned" else native
                self.assertEqual(bytes(current.mem_read(regs[2], len(expected))), expected)

        cpu.hook_add(UC_HOOK_CODE, observe)
        cpu.emu_start(entry | 1, stop, count=100)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), stop)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), stack)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_R4), 0x11223344)
        self.assertEqual(bytes(cpu.mem_read(stack, 24)), b"\xa5" * 24)
        self.assertEqual(bytes(cpu.mem_read(source, len(native))), native)
        self.assertEqual(calls, [decoder] if kind == "invalid" else [decoder, RENDERER])

    def test_owned_text_uses_a_stack_buffer(self):
        self.execute_wrapper("owned")

    def test_native_ram_text_passes_through(self):
        self.execute_wrapper("native")

    def test_invalid_text_cannot_reach_the_renderer(self):
        self.execute_wrapper("invalid")


if __name__ == "__main__":
    unittest.main()

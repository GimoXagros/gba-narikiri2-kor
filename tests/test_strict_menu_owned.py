"""Synthetic ARM7TDMI menu-owner lifetime and passthrough tests."""
import struct
import sys
import unittest
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
    UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4,
    UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_SP)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from strict_menu_owned import (Table, TABLES, JP_ENTRY_BYTES, descriptor_bytes,
    assemble_entry_patch, assemble_trampoline, assemble_wrapper,
    DYNAMIC_CALL_RETURN, DYNAMIC_MAX_COUNT, DYNAMIC_MAX_NATIVE_BYTES,
    MENU_ENTRY)

CODE = 0x080B0000
DESC = 0x080B1000
DECODER = 0x080B2001
ORIGINAL = 0x080B3001
TABLE = 0x080B4000
NATIVE_TABLE = 0x02003000
OWNER = 0x02001000
STACK = 0x03007E00
RETURN = 0x080B7000
RAW = (b"A\0", b"xyz\0")
TABLES_SYNTH = (Table("first", TABLE, 2, sum(len(raw) for raw in RAW),
                      "historical_compact"),)


class MenuOwnedCPU(unittest.TestCase):
    def run_cpu(self, *, source=TABLE, terminated=True, alloc_ok=True,
                decode_ok=True, raw=RAW, dynamic=False, via_entry=False):
        table = Table("synthetic", TABLE, len(raw), sum(map(len, raw)),
                      "historical_compact")
        tables = (table,)
        uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        uc.mem_map(0x08000000, 0x100000)
        uc.mem_map(0x02000000, 0x10000)
        uc.mem_map(0x03000000, 0x8000)
        code = assemble_wrapper(CODE, descriptor_address=DESC,
            decoder=DECODER, original_menu=ORIGINAL, tables=tables)
        self.assertLessEqual(len(code), 272)
        uc.mem_write(CODE, code)
        if via_entry:
            uc.mem_write(MENU_ENTRY, assemble_entry_patch(CODE | 1))
        uc.mem_write(DESC, descriptor_bytes(tables))
        for stub in (DECODER, ORIGINAL, 0x08003521, 0x080035DD):
            uc.mem_write(stub & ~1, b"\x70\x47")  # bx lr
        encoded = tuple(0x080B5000+index*4 for index in range(len(raw)))
        uc.mem_write(TABLE, struct.pack("<"+"I"*(len(raw)+1), *encoded,
                                       0 if terminated else 0x080B6000))
        if dynamic:
            native_before = (struct.pack("<"+"I"*(len(raw)+1), *encoded, 0)
                             if terminated else
                             struct.pack("<"+"I"*(DYNAMIC_MAX_COUNT+1),
                                         *([encoded[0]]*(DYNAMIC_MAX_COUNT+1))))
        else:
            native_before = struct.pack("<II", 0x02004000, 0)
        uc.mem_write(NATIVE_TABLE, native_before)
        uc.mem_write(OWNER-16, b"\xA5"*16)
        owner_allocation = ((len(raw)+1)*4 + DYNAMIC_MAX_NATIVE_BYTES
                            if dynamic else table.allocation)
        uc.mem_write(OWNER+owner_allocation, b"\xA5"*16)
        events = []

        def hook(emu, address, size, _):
            if address == (DYNAMIC_CALL_RETURN & ~1 if dynamic else RETURN):
                emu.emu_stop()
            elif address == 0x08003520:
                requested = emu.reg_read(UC_ARM_REG_R0)
                events.append(("alloc", requested))
                emu.reg_write(UC_ARM_REG_R0, OWNER if alloc_ok else 0)
            elif address == 0x080035DC:
                events.append(("free", emu.reg_read(UC_ARM_REG_R0)))
            elif address == DECODER & ~1:
                src = emu.reg_read(UC_ARM_REG_R0)
                dest = emu.reg_read(UC_ARM_REG_R1)
                limit = emu.reg_read(UC_ARM_REG_R2)
                if src in encoded and decode_ok:
                    output = raw[encoded.index(src)]
                    self.assertGreaterEqual(limit, len(output))
                    emu.mem_write(dest, output)
                    emu.reg_write(UC_ARM_REG_R0, dest)
                    emu.reg_write(UC_ARM_REG_R1, dest)
                    emu.reg_write(UC_ARM_REG_R2, len(output))
                else:
                    emu.reg_write(UC_ARM_REG_R0, src)
                    emu.reg_write(UC_ARM_REG_R1, 0)
                    emu.reg_write(UC_ARM_REG_R2, 0)
            elif address == ORIGINAL & ~1:
                passed = emu.reg_read(UC_ARM_REG_R3)
                events.append(("menu", passed))
                self.assertEqual(emu.reg_read(UC_ARM_REG_R0), 2)
                self.assertEqual(emu.reg_read(UC_ARM_REG_R1), 1)
                self.assertEqual(emu.reg_read(UC_ARM_REG_R2),
                                 14 if dynamic else 7)
                if source == TABLE or dynamic:
                    self.assertEqual(passed, OWNER)
                    ptrbytes = (len(raw)+1)*4
                    starts = []
                    position = OWNER+ptrbytes
                    for output in raw:
                        starts.append(position)
                        position += len(output)
                    self.assertEqual(struct.unpack("<"+"I"*(len(raw)+1),
                                                   emu.mem_read(OWNER, ptrbytes)),
                                     (*starts, 0))
                    self.assertEqual(bytes(emu.mem_read(OWNER+ptrbytes,
                                                       sum(map(len, raw)))),
                                     b"".join(raw))
                else:
                    self.assertEqual(passed, NATIVE_TABLE)
                    self.assertEqual(struct.unpack("<II", emu.mem_read(NATIVE_TABLE, 8)),
                                     (0x02004000, 0))
                emu.reg_write(UC_ARM_REG_R0, 2)

        uc.hook_add(UC_HOOK_CODE, hook)
        for reg, value in ((UC_ARM_REG_R0, 2), (UC_ARM_REG_R1, 1),
                           (UC_ARM_REG_R2, 14 if dynamic else 7),
                           (UC_ARM_REG_R3, source),
                           (UC_ARM_REG_SP, STACK),
                           (UC_ARM_REG_LR, DYNAMIC_CALL_RETURN if dynamic
                            else RETURN | 1)):
            uc.reg_write(reg, value)
        for reg in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7):
            uc.reg_write(reg, 0x12345678)
        uc.emu_start(MENU_ENTRY | 1 if via_entry else CODE | 1, 0,
                     count=100000)
        self.assertEqual(uc.reg_read(UC_ARM_REG_PC) & ~1,
                         DYNAMIC_CALL_RETURN & ~1 if dynamic else RETURN)
        self.assertEqual(uc.reg_read(UC_ARM_REG_SP), STACK)
        for reg in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7):
            self.assertEqual(uc.reg_read(reg), 0x12345678)
        self.assertEqual(bytes(uc.mem_read(OWNER-16, 16)), b"\xA5"*16)
        self.assertEqual(bytes(uc.mem_read(OWNER+owner_allocation, 16)),
                         b"\xA5"*16)
        self.assertEqual(bytes(uc.mem_read(NATIVE_TABLE, len(native_before))),
                         native_before)
        return uc.reg_read(UC_ARM_REG_R0), events

    def test_heap_table_and_native_arena_live_through_menu_then_freed(self):
        result, events = self.run_cpu()
        self.assertEqual(result, 2)
        self.assertEqual(events, [("alloc", 18), ("menu", OWNER), ("free", OWNER)])

    def test_callee_entry_jump_preserves_live_arguments_and_return(self):
        result, events = self.run_cpu(via_entry=True)
        self.assertEqual(result, 2)
        self.assertEqual(events, [("alloc", 18), ("menu", OWNER),
                                  ("free", OWNER)])

    def test_maximum_actual_monster_count_and_native_bytes(self):
        # Largest real strict menu: 164 entries and 2,191 native bytes.
        raw = (b"A"*12+b"\0",)*163 + (b"Z"*71+b"\0",)
        self.assertEqual(sum(map(len, raw)), 2191)
        result, events = self.run_cpu(raw=raw)
        self.assertEqual(result, 2)
        self.assertEqual(events, [("alloc", 2851), ("menu", OWNER),
                                  ("free", OWNER)])

    def test_native_ram_table_passes_without_heap_or_pointer_change(self):
        result, events = self.run_cpu(source=NATIVE_TABLE)
        self.assertEqual(result, 2)
        self.assertEqual(events, [("menu", NATIVE_TABLE)])

    def test_exact_dynamic_stack_caller_gets_owned_copy_without_mutation(self):
        result, events = self.run_cpu(source=NATIVE_TABLE, dynamic=True)
        self.assertEqual(result, 2)
        self.assertEqual(events, [("alloc", 12+DYNAMIC_MAX_NATIVE_BYTES),
                                  ("menu", OWNER), ("free", OWNER)])

    def test_dynamic_table_terminator_guard(self):
        result, events = self.run_cpu(source=NATIVE_TABLE, dynamic=True,
                                      terminated=False)
        self.assertEqual(result, 0xFFFFFFFF)
        self.assertEqual(events, [])

    def test_dynamic_upper_bound_exactly_fills_owned_arena(self):
        raw = (b"K"*16+b"\0",)*DYNAMIC_MAX_COUNT
        self.assertEqual(sum(map(len, raw)), DYNAMIC_MAX_NATIVE_BYTES)
        result, events = self.run_cpu(source=NATIVE_TABLE, dynamic=True,
                                      raw=raw)
        self.assertEqual(result, 2)
        self.assertEqual(events, [("alloc", 14*4+DYNAMIC_MAX_NATIVE_BYTES),
                                  ("menu", OWNER), ("free", OWNER)])

    def test_bad_terminator_frees_owner_and_skips_menu(self):
        result, events = self.run_cpu(terminated=False)
        self.assertEqual(result, 0xFFFFFFFF)
        self.assertEqual(events, [("alloc", 18), ("free", OWNER)])

    def test_allocator_and_decoder_fail_closed(self):
        result, events = self.run_cpu(alloc_ok=False)
        self.assertEqual(result, 0xFFFFFFFF)
        self.assertEqual(events, [("alloc", 18)])
        result, events = self.run_cpu(decode_ok=False)
        self.assertEqual(result, 0xFFFFFFFF)
        self.assertEqual(events, [("alloc", 18), ("free", OWNER)])

    def test_entry_and_original_prologue_contract(self):
        self.assertEqual(len(JP_ENTRY_BYTES), 16)
        patch = assemble_entry_patch(CODE | 1)
        self.assertEqual(len(patch), 16)
        self.assertEqual(patch[-4:], struct.pack("<I", CODE | 1))
        self.assertEqual(assemble_trampoline(0x080B3000)[:16], JP_ENTRY_BYTES)
        self.assertEqual(len(descriptor_bytes(TABLES)), 6*8)
        self.assertEqual(max(t.allocation for t in TABLES), 2851)


if __name__ == "__main__":
    unittest.main()

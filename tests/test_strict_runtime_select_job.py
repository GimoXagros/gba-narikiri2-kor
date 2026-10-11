"""Synthetic CPU contract for the 201-entry SELECT_JOB adapter.

No private translation corpus or diagnostic ROM is required by this test.
"""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest

from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
    UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4,
    UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_SP)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from strict_runtime_select_job import TABLE_ADDRESS, TABLE_OFFSET, ROW_COUNT
from strict_unit_codec import build_book, encode_parts, factor_variants

CODE = 0x01000000
PTRS = 0x02000100
ARENA = 0x02000500
DESC = 0x02002000
BOOK = 0x03000000
STACK = 0x0300F000
RETURN = 0x01001000
ALIASES = ((51, 52), (101, 102), (121, 122),
           (123, 124), (127, 128), (149, 150))


def fixture() -> tuple[bytes, bytes, bytes, list[bytes]]:
    expected = [f"JOB{i:03d}".encode() for i in range(ROW_COUNT)]
    groups = [[raw] for raw in expected]
    for a, b in ALIASES:
        groups[a] = factor_variants([expected[a], expected[b]], "compact")
        groups[b] = groups[a]
    training = [part for i, group in enumerate(groups)
                if i not in {b for _, b in ALIASES} for part in group]
    book = build_book(training, "compact")
    image = bytearray(0x800000)
    desc = bytearray()
    cursor = 0x2C0000
    common = {b: a for a, b in ALIASES}
    starts: dict[int, tuple[int, bytes]] = {}
    for i, group in enumerate(groups):
        canonical = common.get(i, i)
        if canonical not in starts:
            encoded = encode_parts(group, "compact", book)
            starts[canonical] = (cursor, encoded)
            image[cursor:cursor + len(encoded)] = encoded
            cursor += len(encoded)
        start, encoded = starts[canonical]
        struct.pack_into("<I", image, TABLE_OFFSET + i * 4, 0x08000000 + start)
        selection = 13 if i in common else 11 if any(i == a for a, _ in ALIASES) else 1
        desc += struct.pack("<HHBBH", len(encoded), len(expected[i]) + 1,
                            selection, len(group), 0)
    assert cursor < 0x2D0000
    assert sum(len(raw) + 1 for raw in expected) <= 2200
    return bytes(image), bytes(desc), book, expected


class SyntheticSelectJobCPU(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image, cls.desc, cls.book, cls.expected = fixture()
        source = ((ROOT / "asm/strict_runtime_select_job.s").read_text(encoding="utf-8")
                  + "\n" + (ROOT / "asm/strict_unit_bundle_decode.s").read_text(encoding="utf-8"))
        cls.code = bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source, addr=CODE)[0])

    def run_cpu(self, *, source=TABLE_ADDRESS, desc=None, arena_end=ARENA + 2200):
        uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        uc.mem_map(CODE, 0x2000)
        uc.mem_map(0x02000000, 0x10000)
        uc.mem_map(0x03000000, 0x10000)
        uc.mem_map(0x08000000, 0x800000)
        uc.mem_write(CODE, self.code)
        uc.mem_write(0x08000000, self.image)
        uc.mem_write(DESC, self.desc if desc is None else desc)
        uc.mem_write(BOOK, self.book)
        uc.mem_write(ARENA - 16, b"\xA5" * 16)
        uc.mem_write(arena_end, b"\xA5" * 16)
        uc.mem_write(STACK, struct.pack("<IIII", PTRS + 808,
                                         arena_end, BOOK, len(self.book)))
        for reg, value in ((UC_ARM_REG_R0, source), (UC_ARM_REG_R1, DESC),
                           (UC_ARM_REG_R2, PTRS), (UC_ARM_REG_R3, ARENA),
                           (UC_ARM_REG_SP, STACK), (UC_ARM_REG_LR, RETURN | 1)):
            uc.reg_write(reg, value)
        for reg in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7):
            uc.reg_write(reg, 0x12345678)
        def stop(emu, address, size, _):
            if address == RETURN:
                emu.emu_stop()
        uc.hook_add(UC_HOOK_CODE, stop)
        uc.emu_start(CODE | 1, RETURN + 2, count=3_000_000)
        self.assertEqual(uc.reg_read(UC_ARM_REG_PC) & ~1, RETURN)
        self.assertEqual(uc.reg_read(UC_ARM_REG_SP), STACK)
        for reg in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7):
            self.assertEqual(uc.reg_read(reg), 0x12345678)
        self.assertEqual(bytes(uc.mem_read(ARENA - 16, 16)), b"\xA5" * 16)
        self.assertEqual(bytes(uc.mem_read(arena_end, 16)), b"\xA5" * 16)
        return uc

    def test_all_entries_and_six_same_start_aliases(self):
        uc = self.run_cpu()
        self.assertEqual(uc.reg_read(UC_ARM_REG_R0), PTRS)
        used = uc.reg_read(UC_ARM_REG_R1)
        self.assertEqual(used, sum(len(raw) + 1 for raw in self.expected))
        pointers = struct.unpack("<202I", uc.mem_read(PTRS, 808))
        self.assertEqual(pointers[-1], 0)
        for i, raw in enumerate(self.expected):
            self.assertEqual(bytes(uc.mem_read(pointers[i], len(raw) + 1)), raw + b"\0")
        for a, b in ALIASES:
            self.assertEqual(struct.unpack_from("<I", self.image, TABLE_OFFSET + a * 4)[0],
                             struct.unpack_from("<I", self.image, TABLE_OFFSET + b * 4)[0])
            self.assertNotEqual(self.expected[a], self.expected[b])

    def test_wrong_context_and_bounds_fail_closed(self):
        for kwargs in ({"source": TABLE_ADDRESS + 4}, {"arena_end": ARENA + 5}):
            uc = self.run_cpu(**kwargs)
            self.assertEqual(uc.reg_read(UC_ARM_REG_R0), 0)
            self.assertEqual(struct.unpack("<I", uc.mem_read(PTRS, 4))[0], 0)
        bad = bytearray(self.desc)
        bad[51 * 8 + 4] = 0
        uc = self.run_cpu(desc=bytes(bad))
        self.assertEqual(uc.reg_read(UC_ARM_REG_R0), 0)


if __name__ == "__main__":
    unittest.main()

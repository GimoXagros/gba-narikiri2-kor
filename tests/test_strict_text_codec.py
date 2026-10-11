"""Reference and actual ARM7 Thumb execution checks for the strict codec.

Requires keystone, capstone and unicorn from the local validation Python.
These are codec tests, not proof of a game consumer hook or RAM ownership.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from strict_text_codec import CodecError, build_codebook, decode, encode, validate_book

from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_INVALID
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
    UC_ARM_REG_R7, UC_ARM_REG_SP,
)


class ThumbDecoder:
    def __init__(self) -> None:
        source = (ROOT / "asm/strict_text_decode.s").read_text(encoding="utf-8")
        machine, _ = Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source, addr=0x100000)
        self.code = bytes(machine)
        disasm = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(self.code, 0x100000))
        self.mnemonics = {i.mnemonic for i in disasm}
        if sum(i.size for i in disasm) != len(self.code):
            raise AssertionError("decoder contains undecodable machine bytes")

    def run(self, stream: bytes, book: bytes, capacity: int, *, length: int | None = None) -> tuple[int, bytes, int]:
        if not 0 <= len(stream) <= 0x1000 or not 0 <= capacity <= 0x1000:
            raise ValueError("test mapping supports one page")
        uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        for address in (0x100000, 0x200000, 0x300000, 0x400000, 0x500000, 0x600000):
            uc.mem_map(address, 0x1000)
        uc.mem_write(0x100000, self.code)
        src = 0x201000 - len(stream)
        dst = 0x301000 - capacity
        uc.mem_write(src, stream)
        uc.mem_write(0x400000, book)
        stack = 0x500F00
        uc.mem_write(stack, (0x400000).to_bytes(4, "little"))
        initial = {UC_ARM_REG_R4: 0x12345678, UC_ARM_REG_R5: 0x23456789,
                   UC_ARM_REG_R6: 0x3456789A, UC_ARM_REG_R7: 0x456789AB}
        uc.reg_write(UC_ARM_REG_SP, stack)
        uc.reg_write(UC_ARM_REG_LR, 0x600001)
        uc.reg_write(UC_ARM_REG_R0, src)
        uc.reg_write(UC_ARM_REG_R1, len(stream) if length is None else length)
        uc.reg_write(UC_ARM_REG_R2, dst)
        uc.reg_write(UC_ARM_REG_R3, capacity)
        for reg, value in initial.items():
            uc.reg_write(reg, value)
        count = 0
        invalid = []

        def on_code(emulator, address, size, _):
            nonlocal count
            if address == 0x600000:
                emulator.emu_stop()
            else:
                count += 1
                if count > 200000:
                    raise AssertionError("decoder instruction ceiling exceeded")

        def on_invalid(emulator, access, address, size, value, _):
            invalid.append((access, address, size))
            return False

        uc.hook_add(UC_HOOK_CODE, on_code)
        uc.hook_add(UC_HOOK_MEM_INVALID, on_invalid)
        uc.emu_start(0x100001, 0x600002, count=200010)
        if invalid:
            raise AssertionError(f"out-of-bounds memory access {invalid}")
        if uc.reg_read(UC_ARM_REG_SP) != stack:
            raise AssertionError("SP not restored")
        for reg, value in initial.items():
            if uc.reg_read(reg) != value:
                raise AssertionError("callee-saved register changed")
        if uc.reg_read(UC_ARM_REG_PC) & ~1 != 0x600000:
            raise AssertionError("decoder did not return")
        result = uc.reg_read(UC_ARM_REG_R0)
        return result, bytes(uc.mem_read(dst, capacity)), count


class CodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payloads = [b"\x81\x40\x81\x41\n", b"\x81\x40\x81\x42\n", b"\x01\x80\xfe\x7f"]
        cls.book = build_codebook(cls.payloads)
        validate_book(cls.book)
        cls.thumb = ThumbDecoder()

    def test_thumb_is_thumb1_and_abi(self) -> None:
        # ARM7TDMI Thumb-1 has 16-bit instructions only; no BL is needed here.
        self.assertEqual(len(self.thumb.code), 142)
        self.assertTrue(all(i.size == 2 for i in Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(self.thumb.code, 0x100000)))
        self.assertNotIn("bl", self.thumb.mnemonics)
        for payload in self.payloads + [b"", b"\x40" * 24]:
            stream = encode(payload, self.book)
            expected = payload + b"\0"
            self.assertEqual(decode(stream, self.book, len(expected)), expected)
            written, output, count = self.thumb.run(stream, self.book, len(expected))
            self.assertEqual(written, len(expected))
            self.assertEqual(output, expected)
            self.assertLess(count, 3000)

    def test_truncated_bad_token_and_output_limit(self) -> None:
        stream = encode(self.payloads[0], self.book)
        with self.assertRaises(CodecError):
            decode(stream[:-1], self.book, 100)
        self.assertEqual(self.thumb.run(stream[:-1], self.book, 100)[0], 0)
        with self.assertRaises(CodecError):
            decode(stream, self.book, len(self.payloads[0]))
        self.assertEqual(self.thumb.run(stream, self.book, len(self.payloads[0]))[0], 0)
        with self.assertRaises(CodecError):
            decode(b"\0x", self.book, 100)
        self.assertEqual(self.thumb.run(b"\0x", self.book, 100)[0], 0)
        bad_book = bytearray(self.book)
        token = next(b for b in range(1, 256) if b != bad_book[0])
        bad_book[1 + token] = 96
        with self.assertRaises(CodecError):
            decode(bytes((token, 0)), bytes(bad_book), 100)
        self.assertEqual(self.thumb.run(bytes((token, 0)), bytes(bad_book), 100)[0], 0)

    def test_shared_phrase_token_on_thumb(self) -> None:
        corpus = [b"ABCDEFGH"] + [b"ABCDEFGH" + bytes((i,)) for i in range(1, 50)]
        book = build_codebook(corpus)
        token_map = book[1:257]
        self.assertGreater(sum(x != 0xFF for x in token_map), 0)
        for payload in corpus:
            stream = encode(payload, book)
            if payload == b"ABCDEFGH":
                self.assertGreater(len(stream), 2)
            else:
                self.assertTrue(any(token_map[byte] != 0xFF for byte in stream[:-1]))
            expected = payload + b"\0"
            self.assertEqual(decode(stream, book, len(expected)), expected)
            written, output, _ = self.thumb.run(stream, book, len(expected))
            self.assertEqual((written, output), (len(expected), expected))


if __name__ == "__main__":
    unittest.main()

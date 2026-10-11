"""Small read-only Thumb disassembler for AN9J text-consumer investigations.

Addresses are GBA ROM addresses. This intentionally makes no hook or RAM claim.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB

JP_SHA256 = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"


def disassemble(rom: bytes, start: int, end: int) -> list[str]:
    if not 0x08000000 <= start < end <= 0x08800000 or start & 1 or end & 1:
        raise ValueError("Invalid aligned AN9J ROM range")
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    out = []
    for ins in md.disasm(rom[start - 0x08000000:end - 0x08000000], start):
        line = f"{ins.address:08X} {ins.bytes.hex():<8} {ins.mnemonic:<8} {ins.op_str}"
        if ins.mnemonic == "ldr" and ins.op_str.endswith("[pc, #0]"):
            pass
        if ins.mnemonic == "ldr" and "pc" in ins.op_str and ins.operands:
            try:
                disp = ins.operands[-1].mem.disp
                literal = ((ins.address + 4) & ~3) + disp
                if 0x08000000 <= literal <= 0x087FFFFC:
                    word = int.from_bytes(rom[literal - 0x08000000:literal - 0x08000000 + 4], "little")
                    line += f" ; [{literal:08X}]={word:08X}"
            except (AttributeError, IndexError):
                pass
        out.append(line)
    return out


def thumb_bl_xrefs(rom: bytes, target: int, end: int = 0x00400000) -> list[int]:
    """Find aligned Thumb-1 BL sites in the code region, without CFG claims."""
    found = []
    for off in range(0, min(end, len(rom) - 3), 2):
        first = int.from_bytes(rom[off:off + 2], "little")
        second = int.from_bytes(rom[off + 2:off + 4], "little")
        if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
            continue
        disp = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
        if disp & 0x400000:
            disp -= 0x800000
        if 0x08000000 + off + 4 + disp == target:
            found.append(0x08000000 + off)
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("ranges", nargs="*", help="start:end in hex, GBA addresses")
    parser.add_argument("--xref", action="append", default=[], help="Thumb BL target in hex")
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    if len(rom) != 0x800000 or hashlib.sha256(rom).hexdigest() != JP_SHA256:
        raise ValueError("Source is not frozen AN9J JP Rev0")
    for item in args.ranges:
        start_s, end_s = item.split(":")
        start, end = int(start_s, 16), int(end_s, 16)
        print(f"RANGE {start:08X}:{end:08X}")
        print("\n".join(disassemble(rom, start, end)))
    for item in args.xref:
        target = int(item, 16)
        print(f"THUMB_BL_XREF {target:08X}: " + ", ".join(f"{x:08X}" for x in thumb_bl_xrefs(rom, target)))


if __name__ == "__main__":
    main()

"""Symbol-bound ARTE 158/159 diagnostic tags and formatter hook builder."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB

from strict_runtime_select_job import assemble_veneer

ROOT = Path(__file__).resolve().parents[1]
CODE = 0x08C9C200
BOOK = 0x08C9A000
ACCESS_VENEER = 0x0837E1B0
FORMAT_VENEER = 0x0837E1C0
ACCESS_CALL = 0x08008C54
FORMAT_CALL = 0x08002648


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assemble() -> tuple[bytes, int]:
    source = (ROOT / "asm/strict_runtime_arte.s").read_text(encoding="utf-8")
    decoder = (ROOT / "asm/strict_unit_bundle_decode.s").read_text(encoding="utf-8")
    ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
    result = bytearray(ks.asm(source + "\n" + decoder, addr=CODE)[0])
    offset_token = struct.pack("<I", 0xDE5C1000)
    if result.count(offset_token) != 1:
        raise ValueError("ARTE formatter offset marker absent or ambiguous")
    formatter = result.index(offset_token) + 4
    if result[:2] != b"\x30\xB5" or result[formatter:formatter + 2] != b"\xF0\xB5":
        raise ValueError("ARTE entry layout changed")
    token = struct.pack("<I", 0xDE5C0004)
    if result.count(token) != 1:
        raise ValueError("ARTE book marker absent or ambiguous")
    at = result.index(token)
    result[at:at + 4] = struct.pack("<I", BOOK)
    return bytes(result), formatter


def patches() -> dict[int, tuple[bytes, bytes]]:
    payload, formatter_offset = assemble()
    veneer_source = ROOT / "asm/strict_runtime_select_job_veneer.s"
    ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
    access_veneer = assemble_veneer(veneer_source, ACCESS_VENEER, CODE | 1)
    format_veneer = assemble_veneer(veneer_source, FORMAT_VENEER,
                                    (CODE + formatter_offset) | 1)
    access_bl = bytes(ks.asm(f"push {{lr}}; bl 0x{ACCESS_VENEER:08X}", addr=ACCESS_CALL)[0])
    format_bl = bytes(ks.asm(f"push {{lr}}; bl 0x{FORMAT_VENEER:08X}", addr=FORMAT_CALL)[0])
    if len(access_bl) != 6 or len(format_bl) != 6:
        raise ValueError("ARTE entry patches must save LR before Thumb BL")
    return {
        ACCESS_CALL - 0x08000000: (bytes.fromhex("021c002908d0"), access_bl),
        FORMAT_CALL - 0x08000000: (bytes.fromhex("f0b582b0071c"), format_bl),
        ACCESS_VENEER - 0x08000000: (b"\0" * 16, access_veneer),
        FORMAT_VENEER - 0x08000000: (b"\0" * 16, format_veneer),
        CODE - 0x08000000: (b"\0" * len(payload), payload),
    }

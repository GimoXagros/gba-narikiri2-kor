"""Frozen SELECT_JOB descriptor builder and independent staging oracle.

This module derives variant context from the actual 201-entry ROM table index.
It does not allocate game RAM or install a hook. See the Thumb adapter for the
same ABI, and require a proved menu-lifetime arena before patching 0801C3B4.
"""
from __future__ import annotations

import csv
import hashlib
import json
import argparse
import re
import struct
from pathlib import Path

from strict_unit_codec import decode_parts

TABLE_ADDRESS = 0x083AE0E0
TABLE_OFFSET = TABLE_ADDRESS - 0x08000000
ROW_COUNT = 201
POINTER_TABLE_BYTES = (ROW_COUNT + 1) * 4
NATIVE_ARENA_BYTES = 2200
DESCRIPTOR_BYTES = ROW_COUNT * 8


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def descriptors(bindings: list[dict[str, str]], fits: list[dict[str, str]]) -> bytes:
    by_id = {r["binding_id"]: r for r in fits}
    rows = []
    for row in bindings:
        match = re.fullmatch(r"SELECT_JOB_(\d{3}):([0-9A-F]{8})", row["binding_id"])
        if match:
            rows.append((int(match[1]), row))
    rows.sort()
    if len(rows) != ROW_COUNT or [i for i, _ in rows] != list(range(ROW_COUNT)):
        raise ValueError("SELECT_JOB index set is incomplete")
    result = bytearray()
    native_total = 0
    for index, row in rows:
        if int(row["jp_pointer_storage"]) != TABLE_OFFSET + 4 * index:
            raise ValueError(f"SELECT_JOB storage/index mismatch {index}")
        fit = by_id[row["binding_id"]]
        if row["category"] != "compact" or fit["category"] != "compact":
            raise ValueError("SELECT_JOB must use compact native bytes")
        encoded = int(fit["encoded_length"])
        native = int(fit["native_output_length"])
        parts = int(fit["inline_part_count"])
        selection = int(fit["inline_selection"])
        if not (1 <= encoded <= int(row["slot_capacity"]) <= 0xFFFF):
            raise ValueError(f"Invalid encoded slot extent at {index}")
        if not (1 <= native <= 0xFFFF):
            raise ValueError(f"Invalid native extent at {index}")
        if (parts, selection) not in ((1, 1), (4, 11), (4, 13)):
            raise ValueError(f"Unproved selector at {index}")
        native_total += native
        result += struct.pack("<HHBBH", encoded, native, selection, parts, 0)
    if native_total != NATIVE_ARENA_BYTES or len(result) != DESCRIPTOR_BYTES:
        raise ValueError("SELECT_JOB native arena size changed")
    return bytes(result)


def stage(image: bytes, desc: bytes, book: bytes) -> tuple[list[int], bytes]:
    """Reference counterpart of the Thumb adapter; offsets are arena offsets."""
    if len(image) != 0x800000 or len(desc) != DESCRIPTOR_BYTES:
        raise ValueError("Wrong image or descriptor extent")
    if struct.unpack_from("<I", image, TABLE_OFFSET + ROW_COUNT * 4)[0] != 0:
        raise ValueError("SELECT_JOB table sentinel missing")
    pointers, arena = [], bytearray()
    for index in range(ROW_COUNT):
        ptr = struct.unpack_from("<I", image, TABLE_OFFSET + index * 4)[0]
        encoded, native, selection, parts, zero = struct.unpack_from("<HHBBH", desc, index * 8)
        start = ptr - 0x08000000
        if zero or not 0 <= start <= len(image) - encoded:
            raise ValueError(f"Malformed table entry {index}")
        raw, used = decode_parts(image[start:start + encoded], book, native,
                                 parts, selection)
        if used != encoded or len(raw) != native or raw[-1] != 0:
            raise ValueError(f"Native output mismatch at {index}")
        pointers.append(len(arena))
        arena.extend(raw)
    if len(arena) != NATIVE_ARENA_BYTES:
        raise ValueError("SELECT_JOB arena length changed")
    return pointers, bytes(arena)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def assemble_bundle(source: Path, decoder: Path, base: int,
                    descriptor_address: int, book_address: int) -> tuple[bytes, int]:
    """Assemble one relocatable Thumb bundle with two explicit data fixups."""
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
    asm = source.read_text(encoding="utf-8")
    decoder_asm = decoder.read_text(encoding="utf-8")
    ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
    blob = bytearray(ks.asm(asm + "\n" + decoder_asm, addr=base)[0])
    prefix = asm.split("strict_runtime_select_job_menu:")[0]
    wrapper_offset = len(ks.asm(prefix + "\nstrict_unit_bundle_decode: bx lr\n", addr=base)[0]) - 2
    if blob[wrapper_offset:wrapper_offset + 2] != b"\xF0\xB5":
        raise ValueError("Wrapper entry layout changed")
    for marker, address in ((0xDE5C0001, descriptor_address),
                            (0xDE5C0002, book_address)):
        old = struct.pack("<I", marker)
        if blob.count(old) != 1 or not 0x08000000 <= address < 0x0E000000:
            raise ValueError("Invalid or ambiguous runtime relocation")
        start = blob.index(old)
        blob[start:start + 4] = struct.pack("<I", address)
    return bytes(blob), wrapper_offset


def assemble_veneer(source: Path, base: int, far_target: int) -> bytes:
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
    if base & 3 or far_target & 1 != 1:
        raise ValueError("Veneer needs aligned ROM base and Thumb target")
    blob = bytearray(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(
        source.read_text(encoding="utf-8"), addr=base)[0])
    old = struct.pack("<I", 0xDE5C0003)
    if len(blob) != 16 or blob.count(old) != 1:
        raise ValueError("Veneer size or target relocation changed")
    at = blob.index(old)
    blob[at:at + 4] = struct.pack("<I", far_target)
    return bytes(blob)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SELECT_JOB runtime proof artifacts")
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--fit", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--base", type=lambda x: int(x, 0), required=True)
    parser.add_argument("--descriptor-address", type=lambda x: int(x, 0), required=True)
    parser.add_argument("--book-address", type=lambda x: int(x, 0), required=True)
    parser.add_argument("--veneer-base", type=lambda x: int(x, 0))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    desc = descriptors(read_csv(args.bindings), read_csv(args.fit))
    blob, wrapper_offset = assemble_bundle(root / "asm/strict_runtime_select_job.s",
                                           root / "asm/strict_unit_bundle_decode.s",
                                           args.base, args.descriptor_address,
                                           args.book_address)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "SELECT_JOB_DESCRIPTORS.bin").write_bytes(desc)
    (args.out_dir / "SELECT_JOB_RUNTIME_THUMB.bin").write_bytes(blob)
    manifest = {
        "schema": "strict-runtime-select-job-experiment-v1",
        "source_commit": "6caa05608d65d565181474c7e29e6768df07d6a0",
        "table_address": f"0x{TABLE_ADDRESS:08X}",
        "binding_count": ROW_COUNT,
        "pointer_table_ram_bytes": POINTER_TABLE_BYTES,
        "native_arena_ram_bytes": NATIVE_ARENA_BYTES,
        "heap_allocation_bytes": POINTER_TABLE_BYTES + NATIVE_ARENA_BYTES,
        "descriptor_address": f"0x{args.descriptor_address:08X}",
        "descriptor_bytes": len(desc),
        "descriptor_sha256": digest(desc),
        "thumb_base": f"0x{args.base:08X}",
        "thumb_bytes": len(blob),
        "thumb_sha256": digest(blob),
        "prep_entry": f"0x{args.base | 1:08X}",
        "menu_wrapper_entry": f"0x{(args.base + wrapper_offset) | 1:08X}",
        "book_address": f"0x{args.book_address:08X}",
        "status": "CPU_ADAPTER_TESTED__GAME_HOOK_NOT_INSTALLED",
    }
    if args.veneer_base is not None:
        veneer = assemble_veneer(root / "asm/strict_runtime_select_job_veneer.s",
                                  args.veneer_base, (args.base + wrapper_offset) | 1)
        from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
        bl = bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(
            f"bl 0x{args.veneer_base:08X}", addr=0x0801C3B4)[0])
        if len(bl) != 4:
            raise ValueError("SELECT_JOB call patch is not a Thumb BL")
        (args.out_dir / "SELECT_JOB_NEAR_VENEER.bin").write_bytes(veneer)
        (args.out_dir / "SELECT_JOB_CALL_PATCH.bin").write_bytes(bl)
        manifest.update(veneer_address=f"0x{args.veneer_base:08X}",
                        veneer_sha256=digest(veneer), call_site="0x0801C3B4",
                        call_original_hex="e8f7f0fc", call_patch_hex=bl.hex())
    (args.out_dir / "SELECT_JOB_RUNTIME_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()

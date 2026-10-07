"""Lossless, fixed-address full-font page experiment for the AN9J 8 MiB ROM.

The two native 1bpp glyph consumers use ROM literals at 0x1514 and 0x2278.
This plan replaces their direct reads with one 512-byte LZ page on each
call's own stack. It does not license the remaining font suffix until the
actual-game consumer, stack, and timing checks pass.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from find_gba_lz77_asset import decompress_lz77_stream
from narikiri2_item_ui_font import compress_lz77
from strict_layout_core import ROM_BASE, ROM_SIZE, Write, sha
from verify_jp8mib_strict import JP_SHA, KO_SHA

FONT_START = 0xAC3F4
FONT_END = 0xCA3F4
GLYPH_SIZE = 32
GLYPH_COUNT = 3840
PAGE_GLYPHS = 16
PAGE_BYTES = PAGE_GLYPHS * GLYPH_SIZE
PAGE_COUNT = GLYPH_COUNT // PAGE_GLYPHS
WRAPPER_14E0 = 0xB9100
WRAPPER_21F4 = 0xB9200
LOOKUP_221E = 0xB9400
WRAPPER_14E0_32 = 0xB7500
WRAPPER_21F4_32 = 0xB7600
LOOKUP_221E_32 = 0xB7800
NEAR_VENEER = 0x37D9D4
NEAR_VENEER_END = 0x37D9DC
PRODUCT_ARENA_START = 0xB9500
PRODUCT_ARENA_START_32 = 0xB7900


def _align4(value: int) -> int:
    return (value + 3) & ~3


def pack_pages(raw: bytes, *, base: int = FONT_START,
               page_glyphs: int = PAGE_GLYPHS) -> tuple[bytes, dict]:
    if len(raw) != GLYPH_COUNT * GLYPH_SIZE:
        raise ValueError("Full-font source must contain exactly 3,840 32-byte glyphs")
    if page_glyphs not in (16, 32):
        raise ValueError("Only the audited 16/32-glyph page profiles are supported")
    page_bytes = page_glyphs * GLYPH_SIZE
    page_count = GLYPH_COUNT // page_glyphs
    table_end = base + page_count * 4
    cursor = table_end
    entries, streams = [], []
    for index in range(page_count):
        page = raw[index * page_bytes:(index + 1) * page_bytes]
        packed = compress_lz77(page)
        if decompress_lz77_stream(packed, 0, page_bytes) != (page, len(packed)):
            raise ValueError(f"Font page {index} failed LZ round trip")
        cursor = _align4(cursor)
        entries.append(cursor)
        streams.append((cursor, packed))
        cursor += len(packed)
    end = _align4(cursor)
    wrapper_start = WRAPPER_14E0 if page_glyphs == 16 else WRAPPER_14E0_32
    if base == FONT_START and end > wrapper_start:
        raise ValueError("Font pages collide with the consumer-wrapper owner")
    blob = bytearray(end - base)
    for index, offset in enumerate(entries):
        struct.pack_into("<I", blob, index * 4, ROM_BASE + offset)
    for offset, packed in streams:
        blob[offset - base:offset - base + len(packed)] = packed
    for index, pointer in enumerate(entries):
        relative = pointer - base
        decoded, used = decompress_lz77_stream(blob, relative, page_bytes)
        if used != len(streams[index][1]) or decoded != raw[index * page_bytes:(index + 1) * page_bytes]:
            raise ValueError(f"Packed font page {index} changed after layout")
    return bytes(blob), dict(
        source_sha256=sha(raw), glyphs=GLYPH_COUNT, glyph_bytes=GLYPH_SIZE,
        page_glyphs=page_glyphs, page_bytes=page_bytes, page_count=page_count,
        table_start=base, table_end=table_end, packed_end=end,
        packed_bytes=end - base, stream_bytes=sum(len(stream) for _, stream in streams),
        stream_max=max(len(stream) for _, stream in streams),
        owner_end=FONT_END, freed_bytes=FONT_END - end,
        caller_stack_scratch_bytes=page_bytes,
    )


def _assemble(source: str, address: int, maximum: int) -> bytes:
    from keystone import KS_ARCH_ARM, KS_MODE_THUMB, Ks
    from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs

    encoded, _ = Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source, addr=ROM_BASE + address)
    result = bytes(encoded)
    if not 0 < len(result) <= maximum:
        raise ValueError(f"Thumb body at {address:06X} exceeded {maximum} bytes")
    instructions = source.split(".balign", 1)[0].splitlines()
    count = sum(bool(line.strip()) and not line.strip().endswith(":")
                for line in instructions)
    decoded = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(result, ROM_BASE + address))[:count]
    if (len(decoded) != count or any(inst.size != 2 and inst.mnemonic != "bl"
                                    for inst in decoded)
            or any(inst.mnemonic in ("blx", "it", "itt", "cbz", "cbnz", "movw", "movt")
                   for inst in decoded)):
        raise ValueError(f"Thumb-1 instruction-boundary failure at {address:06X}")
    return result


def _entry_jump(destination: int) -> bytes:
    return b"\x00\x4b\x18\x47" + struct.pack("<I", ROM_BASE + destination + 1)


def _near_jump(destination: int) -> bytes:
    # r2 is dead at 0x221E after glyph-index calculation; r3 retains the
    # destination pointer required by 0x2230, so this must not clobber r3.
    return b"\x00\x4a\x10\x47" + struct.pack("<I", ROM_BASE + destination + 1)


WRAPPER_14E0_SOURCE = """
    push {r4, r5, r6, lr}
    sub sp, #508
    sub sp, #20
    str r0, [sp, #512]
    str r1, [sp, #516]
    str r2, [sp, #520]
    lsrs r4, r2, #4
    lsls r4, r4, #2
    ldr r5, font_table
    ldr r0, [r5, r4]
    mov r1, sp
    swi #0x11
    ldr r0, [sp, #512]
    ldr r1, [sp, #516]
    ldr r2, [sp, #520]
    movs r3, #15
    ands r3, r2
    lsls r3, r3, #5
    mov r4, sp
    adds r4, r4, r3
    ldr r5, [sp, #528]
    ldr r3, resume_ptr
    mov lr, r3
    push {r5, lr}
    ldr r3, native_body
    bx r3
resume:
    add sp, #508
    add sp, #20
    ldr r0, [sp, #12]
    pop {r4, r5, r6, pc}
    .balign 4, 0
font_table: .word 0x080ac3f4
native_body: .word 0x080014e9
resume_ptr: .word resume + 1
"""


WRAPPER_21F4_SOURCE = """
    push {r4, r5, r6, r7, lr}
    sub sp, #508
    sub sp, #16
    str r0, [sp, #512]
    str r1, [sp, #516]
    ldrb r4, [r1]
    ldrb r5, [r1, #1]
    cmp r4, #0x87
    bhi upper_lead
    subs r4, #0x81
    b have_lead
upper_lead:
    subs r4, #0x85
have_lead:
    lsls r6, r4, #1
    adds r6, r6, r4
    lsls r6, r6, #6
    adds r6, r6, r5
    subs r6, #0x40
    lsrs r6, r6, #4
    lsls r6, r6, #2
    ldr r7, font_table
    ldr r0, [r7, r6]
    mov r1, sp
    swi #0x11
    ldr r0, [sp, #512]
    ldr r1, [sp, #516]
    ldr r3, resume_ptr
    mov lr, r3
    push {r4, r5, r6, r7, lr}
    mov r7, sl
    mov r6, sb
    mov r5, r8
    ldr r3, native_body
    bx r3
resume:
    add sp, #508
    add sp, #16
    ldr r0, [sp, #16]
    pop {r4, r5, r6, r7, pc}
    .balign 4, 0
font_table: .word 0x080ac3f4
native_body: .word 0x080021fd
resume_ptr: .word resume + 1
"""


LOOKUP_221E_SOURCE = """
    movs r1, #15
    ands r0, r1
    lsls r0, r0, #5
    add r1, sp, #56
    adds r1, r1, r0
    bx lr
"""


WRAPPER_14E0_32_SOURCE = """
    push {r4, r5, r6, lr}
    sub sp, #508
    sub sp, #508
    sub sp, #24
    str r0, [sp]
    str r1, [sp, #4]
    str r2, [sp, #8]
    str r4, [sp, #12]
    lsrs r4, r2, #5
    lsls r4, r4, #2
    ldr r5, font_table
    ldr r0, [r5, r4]
    add r1, sp, #16
    swi #0x11
    ldr r0, [sp]
    ldr r1, [sp, #4]
    ldr r2, [sp, #8]
    movs r3, #31
    ands r3, r2
    lsls r3, r3, #5
    add r4, sp, #16
    adds r4, r4, r3
    ldr r5, [sp, #12]
    ldr r3, resume_ptr
    mov lr, r3
    push {r5, lr}
    ldr r3, native_body
    bx r3
resume:
    add sp, #508
    add sp, #508
    add sp, #24
    ldr r0, [sp, #12]
    pop {r4, r5, r6, pc}
    .balign 4, 0
font_table: .word 0x080ac3f4
native_body: .word 0x080014e9
resume_ptr: .word resume + 1
"""


WRAPPER_21F4_32_SOURCE = """
    push {r4, r5, r6, r7, lr}
    sub sp, #508
    sub sp, #508
    sub sp, #28
    str r0, [sp]
    str r1, [sp, #4]
    ldrb r4, [r1]
    ldrb r5, [r1, #1]
    cmp r4, #0x87
    bhi upper_lead
    subs r4, #0x81
    b have_lead
upper_lead:
    subs r4, #0x85
have_lead:
    lsls r6, r4, #1
    adds r6, r6, r4
    lsls r6, r6, #6
    adds r6, r6, r5
    subs r6, #0x40
    lsrs r6, r6, #5
    lsls r6, r6, #2
    ldr r7, font_table
    ldr r0, [r7, r6]
    add r1, sp, #20
    swi #0x11
    ldr r0, [sp]
    ldr r1, [sp, #4]
    ldr r3, resume_ptr
    mov lr, r3
    push {r4, r5, r6, r7, lr}
    mov r7, sl
    mov r6, sb
    mov r5, r8
    ldr r3, native_body
    bx r3
resume:
    add sp, #508
    add sp, #508
    add sp, #28
    ldr r0, [sp, #16]
    pop {r4, r5, r6, r7, pc}
    .balign 4, 0
font_table: .word 0x080ac3f4
native_body: .word 0x080021fd
resume_ptr: .word resume + 1
"""


LOOKUP_221E_32_SOURCE = """
    movs r1, #31
    ands r0, r1
    lsls r0, r0, #5
    add r1, sp, #76
    adds r1, r1, r0
    bx lr
"""


def plan_font_pages(japanese: bytes, adopted_korean: bytes,
                    *, page_glyphs: int = PAGE_GLYPHS) -> tuple[list[Write], dict]:
    if len(japanese) != ROM_SIZE or sha(japanese) != JP_SHA:
        raise ValueError("Japanese 8 MiB source identity mismatch")
    if len(adopted_korean) != 13270790 or sha(adopted_korean) != KO_SHA:
        raise ValueError("Adopted Korean source identity mismatch")
    for literal in (0x1514, 0x2278):
        if struct.unpack_from("<I", japanese, literal)[0] != ROM_BASE + FONT_START:
            raise ValueError(f"Native font-base literal changed at {literal:X}")
        if japanese[literal:literal + 4] != adopted_korean[literal:literal + 4]:
            raise ValueError(f"Adopted font-base literal changed at {literal:X}")
    # An exact four-byte scan includes unaligned references and all sound/data
    # bytes. The only native font-base references in either source are the two
    # now-retired literals belonging to the hooked renderer instructions.
    needle = struct.pack("<I", ROM_BASE + FONT_START)
    def all_hits(image: bytes) -> list[int]:
        found, cursor = [], 0
        while (cursor := image.find(needle, cursor)) >= 0:
            found.append(cursor)
            cursor += 1
        return found
    code_hits = all_hits(japanese)
    if code_hits != [0x1514, 0x2278] or all_hits(adopted_korean) != code_hits:
        raise ValueError(f"Full-font direct-reference population changed: {code_hits}")
    jp_font = japanese[FONT_START:FONT_END]
    ko_font = adopted_korean[FONT_START:FONT_END]
    changed = [index for index in range(GLYPH_COUNT)
               if jp_font[index * GLYPH_SIZE:(index + 1) * GLYPH_SIZE]
               != ko_font[index * GLYPH_SIZE:(index + 1) * GLYPH_SIZE]]
    if changed != list(range(671, 3021)) + list(range(3024, 3248)):
        raise ValueError("Adopted full-font glyph difference profile changed")
    if page_glyphs == 16:
        wrapper_14, wrapper_21, helper, arena = (
            WRAPPER_14E0, WRAPPER_21F4, LOOKUP_221E, PRODUCT_ARENA_START)
        source_14, source_21, source_helper = (
            WRAPPER_14E0_SOURCE, WRAPPER_21F4_SOURCE, LOOKUP_221E_SOURCE)
        stack_14, stack_21 = 600, 600
    elif page_glyphs == 32:
        wrapper_14, wrapper_21, helper, arena = (
            WRAPPER_14E0_32, WRAPPER_21F4_32, LOOKUP_221E_32,
            PRODUCT_ARENA_START_32)
        source_14, source_21, source_helper = (
            WRAPPER_14E0_32_SOURCE, WRAPPER_21F4_32_SOURCE,
            LOOKUP_221E_32_SOURCE)
        stack_14, stack_21 = 1112, 1120
    else:
        raise ValueError("Unsupported native font page profile")
    font_blob, budget = pack_pages(ko_font, page_glyphs=page_glyphs)
    wrapped_14 = _assemble(source_14, wrapper_14, 0x100)
    wrapped_21 = _assemble(source_21, wrapper_21, 0x100)
    lookup = _assemble(source_helper, helper, 0x40)
    patch_221e = _assemble(f"bl 0x{ROM_BASE + NEAR_VENEER:08x}\nmov r8, r8", 0x221E, 6)
    if len(patch_221e) != 6:
        raise ValueError("Native inline lookup patch must span exactly 6 bytes")
    if FONT_START + len(font_blob) > wrapper_14 or not (
        wrapper_14 + len(wrapped_14) <= wrapper_21
        and wrapper_21 + len(wrapped_21) <= helper
        and helper + len(lookup) <= arena
    ):
        raise ValueError("Font page/wrapper layout overlaps the product arena")
    resource_9_storage = 0x3768F8 + 4 + 9 * 4
    if (0x3768F8 + struct.unpack_from("<I", adopted_korean, resource_9_storage)[0]
            != 0xC80000):
        raise ValueError("Diagnostic title resource has not been relocated")
    if not 0x37D978 <= NEAR_VENEER < NEAR_VENEER_END <= 0x37E36D:
        raise ValueError("Near veneer is outside retired title compression span")
    fields = (
        ("font_pages", FONT_START, font_blob,
         f"{budget['page_count']} lossless Korean full-font pages"),
        ("native_14E0_hook", 0x14E0, _entry_jump(wrapper_14), "native 14E0 entry"),
        ("native_21F4_hook", 0x21F4, _entry_jump(wrapper_21), "native 21F4 entry"),
        ("native_221E_lookup", 0x221E, patch_221e, "per-call stack-page tile selection"),
        ("native_221E_near_veneer", NEAR_VENEER, _near_jump(helper), "near Thumb BL relay"),
        ("native_14E0_wrapper", wrapper_14, wrapped_14, "stack-page decode and native reentry"),
        ("native_21F4_wrapper", wrapper_21, wrapped_21, "stack-page decode and native reentry"),
        ("native_221E_helper", helper, lookup, "stack-relative tile lookup"),
    )
    writes = [Write("asset:" + name, offset, japanese[offset:offset + len(payload)],
                    payload, purpose, "native full-font consumers 080014E0 and 080021F4",
                    "JP exact source, adopted KO font bytes, deterministic page codec",
                    ("source_hash", "page_roundtrip", "native_literal_population", "bounded_owner"))
              for name, offset, payload, purpose in fields]
    budget.update(
        original_jp_font_sha256=sha(jp_font),
        adopted_korean_font_sha256=sha(ko_font),
        changed_glyph_runs=[[671, 3021], [3024, 3248]],
        byte_identical_jp_glyphs=GLYPH_COUNT - len(changed),
        wrapper_14e0=[wrapper_14, wrapper_14 + len(wrapped_14)],
        wrapper_21f4=[wrapper_21, wrapper_21 + len(wrapped_21)],
        lookup_221e=[helper, helper + len(lookup)],
        near_veneer=[NEAR_VENEER, NEAR_VENEER_END],
        code_literals=[0x1514, 0x2278],
        native_entry_hooks=[0x14E0, 0x21F4, 0x221E],
        product_arena=[arena, FONT_END],
        product_arena_bytes=FONT_END - arena,
        stack_max_14e0=stack_14,
        stack_max_21f4=stack_21,
        status="ISOLATED_DIAGNOSTIC_ONLY_PENDING_CPU_AND_GAME_RUNTIME",
    )
    return writes, budget


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--japanese", type=Path, required=True)
    parser.add_argument("--adopted-korean", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--diagnostic-output", type=Path)
    parser.add_argument("--page-glyphs", type=int, choices=(16, 32), default=16)
    args = parser.parse_args()
    jp, ko = args.japanese.read_bytes(), args.adopted_korean.read_bytes()
    writes, budget = plan_font_pages(jp, ko, page_glyphs=args.page_glyphs)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(dict(budget=budget,
                                           writes=[write.manifest() for write in writes]),
                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.diagnostic_output:
        diagnostic = bytearray(ko)
        for write in writes:
            diagnostic[write.start:write.end] = write.after
        args.diagnostic_output.parent.mkdir(parents=True, exist_ok=True)
        args.diagnostic_output.write_bytes(diagnostic)


if __name__ == "__main__":
    main()

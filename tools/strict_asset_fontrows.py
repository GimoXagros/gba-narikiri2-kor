"""Lossless direct-row full-font relocation for the exact AN9J/KO sources.

The original 3,840 x 32-byte 1bpp font is encoded as one 16-bit row mask
and one direct row bytecode stream per glyph. The native consumers decode only
the requested glyph into their own 32-byte stack scratch. Unmodified Japanese
glyphs are included byte-for-byte in the round trip. No persistent RAM is used.

This module proves an isolated asset writeplan; a complete 8 MiB product
requires the other runtime and asset owners to be linked separately.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import struct
from pathlib import Path

from strict_asset_fontpages import _assemble, _entry_jump, _near_jump
from strict_layout_core import ROM_BASE, ROM_SIZE, Write, sha
from verify_jp8mib_strict import JP_SHA, KO_SHA

FONT_START = 0xAC3F4
FONT_END = 0xCA3F4
GLYPHS = 3840
GLYPH_BYTES = 32
MASK_IDS = FONT_START
OFFSETS = 0xAD2F4
STREAM = 0xAF0F4
MASKS = 0xB9CB0
SYMBOLS = 0xB9DBC
PACKED_END = 0xB9FBA
DECODER = 0xB9FC0
WRAPPER_14E0 = 0xBA030
WRAPPER_21F4 = 0xBA070
LOOKUP_221E = 0xBA0C0
ARENA_START = 0xBA0D0
NEAR_VENEER = 0x37D9D4
NEAR_VENEER_END = 0x37D9DC


DECODER_SOURCE = """
push {r4-r7,lr}
ldr r4, mask_ids
ldrb r6, [r4,r0]
ldr r4, offsets
lsls r2, r0, #1
ldrh r2, [r4,r2]
ldr r4, stream
adds r4, r4, r2
ldr r2, masks
lsls r6, r6, #1
ldrh r6, [r2,r6]
mov r5, r1
movs r7, #16
row_loop:
movs r1, #1
tst r6, r1
bne nonzero
movs r1, #0
strh r1, [r5]
b row_done
nonzero:
ldrb r2, [r4]
adds r4, #1
cmp r2, #255
beq escape
ldr r1, symbols
lsls r2, r2, #1
ldrh r2, [r1,r2]
strh r2, [r5]
b row_done
escape:
ldrb r2, [r4]
ldrb r1, [r4, #1]
lsls r1, r1, #8
orrs r1, r2
strh r1, [r5]
adds r4, #2
row_done:
adds r5, #2
lsrs r6, r6, #1
subs r7, #1
bne row_loop
pop {r4-r7,pc}
.balign 4, 0
mask_ids: .word 0x080AC3F4
offsets: .word 0x080AD2F4
stream: .word 0x080AF0F4
masks: .word 0x080B9CB0
symbols: .word 0x080B9DBC
"""

WRAPPER_14E0_SOURCE = """
push {r4,r5,r6,lr}
sub sp, #48
str r0, [sp, #32]
str r1, [sp, #36]
str r2, [sp, #40]
mov r0, r2
mov r1, sp
bl 0x080B9FC0
ldr r0, [sp, #32]
ldr r1, [sp, #36]
ldr r2, [sp, #40]
mov r4, sp
ldr r5, [sp, #48]
ldr r3, resume_ptr
mov lr, r3
push {r5,lr}
ldr r3, native_body
bx r3
resume:
add sp, #48
ldr r0, [sp, #12]
pop {r4,r5,r6,pc}
.balign 4, 0
native_body: .word 0x080014E9
resume_ptr: .word resume + 1
"""

WRAPPER_21F4_SOURCE = """
push {r4,r5,r6,r7,lr}
sub sp, #48
str r0, [sp, #32]
str r1, [sp, #36]
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
mov r0, r6
mov r1, sp
bl 0x080B9FC0
ldr r0, [sp, #32]
ldr r1, [sp, #36]
ldr r3, resume_ptr
mov lr, r3
push {r4,r5,r6,r7,lr}
mov r7, sl
mov r6, sb
mov r5, r8
ldr r3, native_body
bx r3
resume:
add sp, #48
ldr r0, [sp, #16]
pop {r4,r5,r6,r7,pc}
.balign 4, 0
native_body: .word 0x080021FD
resume_ptr: .word resume + 1
"""

LOOKUP_SOURCE = """
add r1, sp, #56
bx lr
"""


def pack_font_rows(raw: bytes) -> tuple[bytes, dict]:
    if len(raw) != GLYPHS * GLYPH_BYTES:
        raise ValueError("Full native font must be 3,840 x 32 bytes")
    glyphs = [raw[i:i + GLYPH_BYTES] for i in range(0, len(raw), GLYPH_BYTES)]
    rows = [[glyph[i:i + 2] for i in range(0, GLYPH_BYTES, 2)]
            for glyph in glyphs]
    masks = [sum((row != b"\0\0") << i for i, row in enumerate(glyph))
             for glyph in rows]
    mask_values = sorted(set(masks))
    if len(mask_values) > 256:
        raise ValueError("Native row masks exceed one-byte index")
    mask_index = {mask: i for i, mask in enumerate(mask_values)}
    frequency = Counter(row for glyph in rows for row in glyph if row != b"\0\0")
    symbols = [row for row, _ in sorted(frequency.items(),
                 key=lambda pair: (-pair[1], pair[0]))[:255]]
    symbol_index = {row: i for i, row in enumerate(symbols)}
    ids = bytes(mask_index[mask] for mask in masks)
    offsets = bytearray()
    stream = bytearray()
    escaped = 0
    max_glyph_stream = 0
    for glyph in rows:
        if len(stream) >= 65536:
            raise ValueError("Per-glyph offsets exceed 16 bits")
        offsets.extend(struct.pack("<H", len(stream)))
        start = len(stream)
        for row in glyph:
            if row == b"\0\0":
                continue
            if row in symbol_index:
                stream.append(symbol_index[row])
            else:
                stream.extend(b"\xff" + row)
                escaped += 1
        max_glyph_stream = max(max_glyph_stream, len(stream) - start)
    if len(stream) >= 65536:
        raise ValueError("Packed row stream exceeds 16-bit offsets")
    stream.extend(b"\0\0")  # Bounded two-byte escape lookahead at stream end.
    pieces = (ids, bytes(offsets), bytes(stream),
              b"".join(struct.pack("<H", mask) for mask in mask_values),
              b"".join(symbols))
    blob = b"".join(pieces)
    if unpack_font_rows(blob, len(mask_values), len(symbols)) != raw:
        raise ValueError("All-glyph row-codec round trip changed a byte")
    return blob, dict(raw_sha256=sha(raw), glyphs=GLYPHS,
                      mask_values=len(mask_values), row_values=len(frequency),
                      dictionary_rows=len(symbols), escaped_rows=escaped,
                      max_glyph_stream_bytes=max_glyph_stream,
                      section_bytes=list(map(len, pieces)), packed_bytes=len(blob),
                      packed_sha256=sha(blob))


def unpack_font_rows(blob: bytes, mask_count: int, symbol_count: int) -> bytes:
    if not 0 <= mask_count <= 256 or not 0 <= symbol_count <= 255:
        raise ValueError("Invalid row table size")
    ids = blob[:GLYPHS]
    offsets = blob[GLYPHS:GLYPHS + GLYPHS * 2]
    mask_bytes = mask_count * 2
    symbol_bytes = symbol_count * 2
    if len(blob) < GLYPHS * 3 + 2 + mask_bytes + symbol_bytes:
        raise ValueError("Packed font is truncated")
    symbol_start = len(blob) - symbol_bytes
    mask_start = symbol_start - mask_bytes
    stream = blob[GLYPHS * 3:mask_start]
    masks = [struct.unpack_from("<H", blob, mask_start + i * 2)[0]
             for i in range(mask_count)]
    symbols = [blob[symbol_start + i * 2:symbol_start + i * 2 + 2]
               for i in range(symbol_count)]
    output = bytearray()
    for glyph in range(GLYPHS):
        mask_id = ids[glyph]
        if mask_id >= len(masks):
            raise ValueError("Glyph mask index out of range")
        mask = masks[mask_id]
        at = struct.unpack_from("<H", offsets, glyph * 2)[0]
        for row in range(16):
            if not mask & (1 << row):
                output.extend(b"\0\0")
                continue
            if at >= len(stream):
                raise ValueError("Glyph row stream runs past owner")
            code = stream[at]
            at += 1
            if code == 255:
                if at + 2 > len(stream):
                    raise ValueError("Raw row escape runs past owner")
                output.extend(stream[at:at + 2])
                at += 2
            elif code < len(symbols):
                output.extend(symbols[code])
            else:
                raise ValueError("Glyph row symbol out of range")
    return bytes(output)


def plan_font_rows(japanese: bytes, adopted_korean: bytes) -> tuple[list[Write], dict]:
    if len(japanese) != ROM_SIZE or sha(japanese) != JP_SHA:
        raise ValueError("Japanese 8 MiB source identity mismatch")
    if len(adopted_korean) != 13270790 or sha(adopted_korean) != KO_SHA:
        raise ValueError("Adopted Korean source identity mismatch")
    needle = struct.pack("<I", ROM_BASE + FONT_START)
    def refs(image: bytes) -> list[int]:
        result, at = [], 0
        while (at := image.find(needle, at)) >= 0:
            result.append(at)
            at += 1
        return result
    if refs(japanese) != [0x1514, 0x2278] or refs(adopted_korean) != [0x1514, 0x2278]:
        raise ValueError("Native full-font pointer population changed")
    jp_font = japanese[FONT_START:FONT_END]
    ko_font = adopted_korean[FONT_START:FONT_END]
    changed = [i for i in range(GLYPHS)
               if jp_font[i * GLYPH_BYTES:(i + 1) * GLYPH_BYTES]
               != ko_font[i * GLYPH_BYTES:(i + 1) * GLYPH_BYTES]]
    if changed != list(range(671, 3021)) + list(range(3024, 3248)):
        raise ValueError("Full-font adopted Korean difference profile changed")
    blob, codec = pack_font_rows(ko_font)
    if len(blob) != 56262 or FONT_START + len(blob) != PACKED_END:
        raise ValueError("Exact font row payload layout changed")
    decoder = _assemble(DECODER_SOURCE, DECODER, WRAPPER_14E0 - DECODER)
    wrapper14 = _assemble(WRAPPER_14E0_SOURCE, WRAPPER_14E0,
                          WRAPPER_21F4 - WRAPPER_14E0)
    wrapper21 = _assemble(WRAPPER_21F4_SOURCE, WRAPPER_21F4,
                          LOOKUP_221E - WRAPPER_21F4)
    lookup = _assemble(LOOKUP_SOURCE, LOOKUP_221E, ARENA_START - LOOKUP_221E)
    if not (len(decoder) == 100 and len(wrapper14) == 52
            and len(wrapper21) == 76 and len(lookup) == 4
            and PACKED_END <= DECODER
            and DECODER + len(decoder) <= WRAPPER_14E0
            and WRAPPER_14E0 + len(wrapper14) <= WRAPPER_21F4
            and WRAPPER_21F4 + len(wrapper21) <= LOOKUP_221E
            and LOOKUP_221E + len(lookup) <= ARENA_START < FONT_END):
        raise ValueError("Direct-row decoder/wrapper owner overlap")
    patch221e = _assemble(f"bl 0x{ROM_BASE + NEAR_VENEER:08x}\nmov r8,r8", 0x221E, 6)
    if len(patch221e) != 6:
        raise ValueError("Native font lookup hook span changed")
    if not 0x37D978 <= NEAR_VENEER < NEAR_VENEER_END <= 0x37E36D:
        raise ValueError("Font near veneer leaves retired title resource suffix")
    resource_9_storage = 0x3768F8 + 4 + 9 * 4
    if (0x3768F8 + struct.unpack_from("<I", adopted_korean, resource_9_storage)[0]
            != 0xC80000):
        raise ValueError("Adopted title compression owner has not been relocated")
    fields = (
        ("font_rows", FONT_START, blob, "lossless complete Korean 1bpp font"),
        ("native_14E0_hook", 0x14E0, _entry_jump(WRAPPER_14E0), "native glyph renderer entry"),
        ("native_21F4_hook", 0x21F4, _entry_jump(WRAPPER_21F4), "native glyph converter entry"),
        ("native_221E_lookup", 0x221E, patch221e, "32-byte stack glyph lookup"),
        ("native_221E_near_veneer", NEAR_VENEER, _near_jump(LOOKUP_221E),
         "Thumb BL relay in retired title stream"),
        ("native_row_decoder", DECODER, decoder, "single-glyph row decode"),
        ("native_14E0_wrapper", WRAPPER_14E0, wrapper14, "caller-owned stack glyph"),
        ("native_21F4_wrapper", WRAPPER_21F4, wrapper21, "caller-owned stack glyph"),
        ("native_221E_helper", LOOKUP_221E, lookup, "native converter stack lookup"),
    )
    writes = [Write("asset:" + name, offset, japanese[offset:offset + len(payload)],
                    payload, purpose, "native 080014E0 and 080021F4 consumers",
                    "exact JP/KO source and full-font round trip",
                    ("source_hash", "all_glyphs", "two_literal_refs", "bounded_owner"))
              for name, offset, payload, purpose in fields]
    for a, b in zip(sorted(writes, key=lambda row: row.start),
                    sorted(writes, key=lambda row: row.start)[1:]):
        if a.end > b.start:
            raise ValueError("Overlapping font writeplan")
    report = dict(status="ISOLATED_FONT_DIAGNOSTIC_NOT_COMPLETE_PRODUCT",
                  codec=codec, original_jp_font_sha256=sha(jp_font),
                  adopted_korean_font_sha256=sha(ko_font),
                  byte_identical_jp_glyphs=GLYPHS - len(changed),
                  changed_glyph_runs=[[671, 3021], [3024, 3248]],
                  row_sections={"ids": [MASK_IDS, OFFSETS],
                                "offsets": [OFFSETS, STREAM],
                                "stream": [STREAM, MASKS],
                                "masks": [MASKS, SYMBOLS],
                                "symbols": [SYMBOLS, PACKED_END]},
                  decoder=[DECODER, DECODER + len(decoder)],
                  wrapper14=[WRAPPER_14E0, WRAPPER_14E0 + len(wrapper14)],
                  wrapper21=[WRAPPER_21F4, WRAPPER_21F4 + len(wrapper21)],
                  lookup=[LOOKUP_221E, LOOKUP_221E + len(lookup)],
                  near_veneer=[NEAR_VENEER, NEAR_VENEER_END],
                  product_arena=[ARENA_START, FONT_END],
                  product_arena_bytes=FONT_END - ARENA_START,
                  caller_stack_scratch_bytes=32,
                  stack_low_canary_at_sp_minus_bytes=264,
                  title_owner_condition="resource 9 redirected to C80000 before near veneer use")
    return writes, report


def assemble_diagnostic(japanese: bytes, adopted_korean: bytes) -> tuple[bytes, dict]:
    writes, report = plan_font_rows(japanese, adopted_korean)
    output = bytearray(adopted_korean)
    for row in writes:
        output[row.start:row.end] = row.after
    if len(output) != len(adopted_korean):
        raise ValueError("Diagnostic source size changed")
    return bytes(output), dict(report, diagnostic_sha256=sha(output),
                               writes=[row.manifest() for row in writes])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--japanese", type=Path, required=True)
    parser.add_argument("--adopted-korean", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--diagnostic-output", type=Path)
    args = parser.parse_args()
    jp, ko = args.japanese.read_bytes(), args.adopted_korean.read_bytes()
    if args.diagnostic_output:
        image, report = assemble_diagnostic(jp, ko)
        args.diagnostic_output.parent.mkdir(parents=True, exist_ok=True)
        args.diagnostic_output.write_bytes(image)
    else:
        writes, plan = plan_font_rows(jp, ko)
        report = dict(plan, writes=[row.manifest() for row in writes])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()

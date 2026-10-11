"""Exact 8-glyph-offset-block variant of the lossless direct-row font.

The bytecode for every glyph is unchanged from strict_asset_fontrows. A
two-byte base per eight glyphs and one-byte lengths reduce the index by 2,880
bytes. The decoder sums at most seven lengths before the same row expansion.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from strict_asset_fontrows import (
    FONT_START, FONT_END, GLYPHS, NEAR_VENEER, NEAR_VENEER_END,
    WRAPPER_14E0_SOURCE, WRAPPER_21F4_SOURCE, LOOKUP_SOURCE,
    pack_font_rows, unpack_font_rows, plan_font_rows,
)
from strict_asset_fontpages import _assemble, _entry_jump, _near_jump
from strict_layout_core import ROM_BASE, Write, sha

GROUP_BASES = 0xAD2F4
LENGTHS = 0xAD6B4
STREAM = 0xAE5B4
MASKS = 0xB9170
SYMBOLS = 0xB927C
PACKED_END = 0xB947A
DECODER = 0xB9490
WRAPPER_14E0 = 0xB9520
WRAPPER_21F4 = 0xB9560
LOOKUP_221E = 0xB95B0
ARENA_START = 0xB95C0

DECODER_SOURCE = """
push {r4-r7,lr}
mov r5, r1
ldr r4, mask_ids
ldrb r6, [r4,r0]
mov r7, r0
lsrs r2, r0, #3
ldr r4, group_bases
lsls r1, r2, #1
ldrh r1, [r4,r1]
ldr r4, stream
adds r4, r4, r1
lsls r2, r2, #3
subs r7, r7, r2
ldr r1, lengths
adds r1, r1, r2
offset_loop:
cmp r7, #0
beq offset_done
ldrb r2, [r1]
adds r1, #1
adds r4, r4, r2
subs r7, #1
b offset_loop
offset_done:
ldr r2, masks
lsls r6, r6, #1
ldrh r6, [r2,r6]
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
group_bases: .word 0x080AD2F4
lengths: .word 0x080AD6B4
stream: .word 0x080AE5B4
masks: .word 0x080B9170
symbols: .word 0x080B927C
"""


def pack_font_rows8(raw: bytes) -> tuple[bytes, dict]:
    direct, original = pack_font_rows(raw)
    ids = direct[:GLYPHS]
    offsets = direct[GLYPHS:GLYPHS * 3]
    stream_length = original["section_bytes"][2]
    stream = direct[GLYPHS * 3:GLYPHS * 3 + stream_length]
    tables = direct[GLYPHS * 3 + stream_length:]
    original_offsets = [struct.unpack_from("<H", offsets, i * 2)[0]
                        for i in range(GLYPHS)]
    ends = original_offsets[1:] + [len(stream) - 2]
    lengths = [end - start for start, end in zip(original_offsets, ends)]
    if not all(0 <= length <= 255 for length in lengths):
        raise ValueError("A glyph exceeds the one-byte length table")
    bases = b"".join(struct.pack("<H", original_offsets[i])
                     for i in range(0, GLYPHS, 8))
    pieces = ids, bases, bytes(lengths), stream, tables
    blob = b"".join(pieces)
    if unpack_font_rows8(blob, original["mask_values"],
                         original["dictionary_rows"]) != raw:
        raise ValueError("Eight-glyph block row round trip changed a byte")
    return blob, dict(original, block_glyphs=8, group_base_bytes=len(bases),
                      length_bytes=len(lengths), section_bytes=[len(p) for p in pieces],
                      packed_bytes=len(blob), packed_sha256=sha(blob))


def unpack_font_rows8(blob: bytes, mask_count: int, symbol_count: int) -> bytes:
    if len(blob) < GLYPHS + GLYPHS // 8 * 2 + GLYPHS + 2:
        raise ValueError("Eight-glyph block font is truncated")
    ids = blob[:GLYPHS]
    base_start = GLYPHS
    length_start = base_start + GLYPHS // 8 * 2
    stream_start = length_start + GLYPHS
    bases = blob[base_start:length_start]
    lengths = blob[length_start:stream_start]
    offsets = bytearray()
    for group in range(GLYPHS // 8):
        at = struct.unpack_from("<H", bases, group * 2)[0]
        for i in range(group * 8, group * 8 + 8):
            if at >= 65536:
                raise ValueError("Eight-glyph block offset overflow")
            offsets.extend(struct.pack("<H", at))
            at += lengths[i]
    direct = ids + bytes(offsets) + blob[stream_start:]
    return unpack_font_rows(direct, mask_count, symbol_count)


def plan_font_rows8(japanese: bytes, adopted_korean: bytes) -> tuple[list[Write], dict]:
    # Full source, original-font reference, title-owner, and changed-glyph
    # contracts are shared with the independently tested direct-offset plan.
    _, inherited = plan_font_rows(japanese, adopted_korean)
    raw = adopted_korean[FONT_START:FONT_END]
    blob, codec = pack_font_rows8(raw)
    if len(blob) != 53382 or FONT_START + len(blob) != PACKED_END:
        raise ValueError("Exact eight-glyph font payload layout changed")
    decoder = _assemble(DECODER_SOURCE, DECODER, WRAPPER_14E0 - DECODER)
    wrapper14 = _assemble(WRAPPER_14E0_SOURCE.replace("0x080B9FC0", "0x080B9490"),
                          WRAPPER_14E0, WRAPPER_21F4 - WRAPPER_14E0)
    wrapper21 = _assemble(WRAPPER_21F4_SOURCE.replace("0x080B9FC0", "0x080B9490"),
                          WRAPPER_21F4, LOOKUP_221E - WRAPPER_21F4)
    lookup = _assemble(LOOKUP_SOURCE, LOOKUP_221E, ARENA_START - LOOKUP_221E)
    if not (len(decoder) == 128 and len(wrapper14) == 52 and len(wrapper21) == 76
            and len(lookup) == 4 and PACKED_END <= DECODER
            and DECODER + len(decoder) <= WRAPPER_14E0
            and WRAPPER_14E0 + len(wrapper14) <= WRAPPER_21F4
            and WRAPPER_21F4 + len(wrapper21) <= LOOKUP_221E
            and LOOKUP_221E + len(lookup) <= ARENA_START < FONT_END):
        raise ValueError("Eight-glyph font decoder/wrapper owner overlap")
    patch221e = _assemble(f"bl 0x{ROM_BASE + NEAR_VENEER:08x}\nmov r8,r8", 0x221E, 6)
    fields = (
        ("font_rows8", FONT_START, blob, "lossless complete Korean 1bpp font"),
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
    ordered = sorted(writes, key=lambda row: row.start)
    if any(a.end > b.start for a, b in zip(ordered, ordered[1:])):
        raise ValueError("Overlapping eight-glyph font writeplan")
    report = dict(inherited, codec=codec, status="ISOLATED_FONT_DIAGNOSTIC_NOT_COMPLETE_PRODUCT",
                  row_sections={"ids": [FONT_START, GROUP_BASES],
                                "group_bases": [GROUP_BASES, LENGTHS],
                                "lengths": [LENGTHS, STREAM],
                                "stream": [STREAM, MASKS],
                                "masks": [MASKS, SYMBOLS],
                                "symbols": [SYMBOLS, PACKED_END]},
                  decoder=[DECODER, DECODER + len(decoder)],
                  wrapper14=[WRAPPER_14E0, WRAPPER_14E0 + len(wrapper14)],
                  wrapper21=[WRAPPER_21F4, WRAPPER_21F4 + len(wrapper21)],
                  lookup=[LOOKUP_221E, LOOKUP_221E + len(lookup)],
                  near_veneer=[NEAR_VENEER, NEAR_VENEER_END],
                  product_arena=[ARENA_START, FONT_END],
                  product_arena_bytes=FONT_END - ARENA_START)
    return writes, report


def assemble_diagnostic8(japanese: bytes, adopted_korean: bytes) -> tuple[bytes, dict]:
    writes, report = plan_font_rows8(japanese, adopted_korean)
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
        image, report = assemble_diagnostic8(jp, ko)
        args.diagnostic_output.parent.mkdir(parents=True, exist_ok=True)
        args.diagnostic_output.write_bytes(image)
    else:
        writes, plan = plan_font_rows8(jp, ko)
        report = dict(plan, writes=[row.manifest() for row in writes])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()

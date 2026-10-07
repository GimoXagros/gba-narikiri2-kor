"""Owned in-place title assets for the AN9J 8 MiB product linker.

This is a write-plan supplier, not a playable ROM builder. The title resource
table uses offsets relative to 0x3768F8. Both Korean LZ streams fit inside the
corresponding Japanese streams, so their table entries remain byte-identical.
Callers must combine these writes with all other product writes and prove the
whole product's runtime/reference closure before releasing an image.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from find_gba_lz77_asset import decompress_lz77_stream
from gba_rl import decompress as decompress_rl
from strict_layout_core import ROM_BASE, ROM_SIZE, Write, sha
from verify_jp8mib_strict import KO_SHA, JP_SHA

TABLE = 0x3768F8
RESOURCE_COUNT = 19
# Existing table indexes, stream starts, and bounded consumed lengths. The
# lengths are checked again against the exact source ROMs on every invocation.
RESOURCES = (
    (9, "korean_title", 0x37C09C, 8913, 0xC80000, 6364),
    (16, "copyright", 0x37EBE8, 2040, 0xC84000, 1134),
)
SAVE_POINTER = 0xA1E4
SAVE_SIGNATURE = 0x2BF4C8
TITLE_VENEER_START = 0x37D980
TITLE_VENEER_END = 0x37D990
SMALL_FONT_START = 0x0CA3F4
SMALL_FONT_RESERVED_END = 0x0CABC4
SMALL_FONT_KO_START = 0xC18000
STAFF_WRAPPER_START = 0x37D9A0
STAFF_FONT_START = 0x37D9E0
STAFF_HOOK_STORAGE = 0xA59CC
CREDITS_START = 0x37F058
CREDITS_OLD_START = 0xC85000
CREDITS_LENGTH = 873


def _lz(image: bytes, start: int, maximum: int) -> tuple[bytes, int]:
    value = decompress_lz77_stream(image, start, maximum)
    if value is None:
        raise ValueError(f"Invalid bounded LZ stream at {start:08X}")
    return value


def _table_starts(image: bytes, *, ordered: bool) -> list[int]:
    offsets = [struct.unpack_from("<I", image, TABLE + 4 + index * 4)[0]
               for index in range(RESOURCE_COUNT)]
    starts = [TABLE + offset for offset in offsets]
    if not all(TABLE + 4 + RESOURCE_COUNT * 4 <= start < len(image)
               for start in starts):
        raise ValueError("Title resource table has an out-of-range entry")
    if len(set(starts)) != RESOURCE_COUNT or (ordered and starts != sorted(starts)):
        raise ValueError("Title resource table ownership changed")
    return starts


def _direct_pointer_hits(image: bytes, begin: int, end: int) -> list[int]:
    """Conservative aligned absolute-pointer scan, including stream interiors."""
    hits = []
    for storage in range(0, len(image) - 3, 4):
        value = struct.unpack_from("<I", image, storage)[0]
        if ROM_BASE + begin <= value < ROM_BASE + end:
            hits.append(storage)
    return hits


def validate_reclaimed_suffix(new_end: int, old_end: int,
                              owned_spans: tuple[tuple[int, int], ...]) -> None:
    """Reject a placement crossing compressed input or another reused owner."""
    if not 0 <= new_end < old_end <= ROM_SIZE or not owned_spans:
        raise ValueError("Invalid reclaimed compressed-stream suffix")
    spans = sorted(owned_spans)
    for start, end in spans:
        if not new_end <= start < end <= old_end:
            raise ValueError("Placement outside reclaimed suffix")
    if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
        raise ValueError("Overlapping reclaimed-suffix owners")


def plan_title_assets(japanese: bytes, adopted_korean: bytes) -> tuple[list[Write], dict]:
    if len(japanese) != ROM_SIZE or sha(japanese) != JP_SHA:
        raise ValueError("Japanese source identity mismatch")
    if len(adopted_korean) != 13270790 or sha(adopted_korean) != KO_SHA:
        raise ValueError("Adopted Korean source identity mismatch")
    jp_starts = _table_starts(japanese, ordered=True)
    ko_starts = _table_starts(adopted_korean, ordered=False)
    if japanese[SAVE_SIGNATURE:SAVE_SIGNATURE + 8] != b"NARIKIRI":
        raise ValueError("Original save signature changed")
    if struct.unpack_from("<I", japanese, SAVE_POINTER)[0] != ROM_BASE + SAVE_SIGNATURE:
        raise ValueError("Original save signature pointer changed")
    if (japanese[0xA1C8:0xA1E4] != adopted_korean[0xA1C8:0xA1E4]
            or japanese[0xA6024:0xA6028] != adopted_korean[0xA6024:0xA6028]):
        raise ValueError("Save signature copy consumer changed")
    writes, proof = [], []
    for index, name, jp_start, jp_used, ko_start, ko_used in RESOURCES:
        if jp_starts[index] != jp_start or ko_starts[index] != ko_start:
            raise ValueError(f"{name}: title resource table pointer changed")
        raw_jp, actual_jp_used = decompress_rl(japanese, jp_start, 0x20000)
        raw_ko, actual_ko_used = _lz(adopted_korean, ko_start, 0x20000)
        if (actual_jp_used, actual_ko_used) != (jp_used, ko_used):
            raise ValueError(f"{name}: compressed stream extent changed")
        if len(raw_jp) != len(raw_ko) or ko_used > jp_used:
            raise ValueError(f"{name}: decoded geometry or in-place fit changed")
        next_start = jp_starts[index + 1]
        if jp_start + jp_used > next_start:
            raise ValueError(f"{name}: Japanese stream overlaps next table resource")
        # Relative table entries account for each resource start. An aligned
        # absolute pointer into either *consumed* stream would need a separate
        # caller proof; fail closed instead of silently leaving it stale.
        direct = _direct_pointer_hits(japanese, jp_start, jp_start + jp_used)
        if direct:
            raise ValueError(f"{name}: absolute reference into source stream: {direct}")
        payload = adopted_korean[ko_start:ko_start + ko_used]
        if _lz(payload, 0, 0x20000) != (raw_ko, ko_used):
            raise ValueError(f"{name}: extracted stream is not self-contained")
        writes.append(Write(
            writer_id=f"asset:title_resource_{index}", start=jp_start,
            before=japanese[jp_start:jp_start + ko_used], after=payload,
            purpose=f"lossless {name} LZ stream at original resource start",
            consumer=f"relative title resource table index {index} at {TABLE + 4 + index * 4:08X}",
            provenance="exact adopted Korean stream and exact AN9J Japanese source",
            tests=("source_identity", "relative_table", "bounded_lz_decode",
                   "next_resource_boundary", "aligned_absolute_pointer_scan"),
        ))
        proof.append(dict(resource=index, name=name,
                          table_storage=f"{TABLE + 4 + index * 4:08X}",
                          original_start=f"{jp_start:08X}",
                          jp_consumed_bytes=jp_used, korean_consumed_bytes=ko_used,
                          original_next_resource=f"{next_start:08X}",
                          decoded_bytes=len(raw_ko), decoded_sha256=sha(raw_ko),
                          stream_sha256=sha(payload), absolute_pointer_hits=direct,
                          final_relative_pointer_unchanged=True))
    return writes, dict(status="IN_PLACE_ASSET_WRITES_READY_FOR_PRODUCT_LINK",
                        source_sha256=JP_SHA, adopted_sha256=KO_SHA,
                        assets=proof, total_written_bytes=sum(len(w.after) for w in writes),
                        consumer_evidence=(
                            "080033FC reads a bounded index from the relative resource table; "
                            "080033AC reads stream header type and dispatches type 1 to "
                            "080A603C (LZ) or type 3 to 080A6048 (RL); "
                            "0800A7B8 and 0800A7E8 load the title resource table literal"),
                        save_signature=dict(pointer_storage=f"{SAVE_POINTER:08X}",
                            original_source=f"{SAVE_SIGNATURE:08X}",
                            value_unchanged=True, signature_sha256=sha(b"NARIKIRI")),
                        remaining_gate="full dynamic reference closure and product runtime validation")


def title_veneer_owner(japanese: bytes, adopted_korean: bytes) -> dict:
    """Prove a 16-byte near-BL veneer slot in resource #9's retired suffix.

    The diagnostic expanded baseline already repoints resource #9 to C80000.
    A final JP-based build must first install the in-place Korean LZ stream;
    then the old RL suffix is beyond that stream's consumed end. Neither
    profile licenses writing elsewhere in the source asset.
    """
    _, plan = plan_title_assets(japanese, adopted_korean)
    title = plan["assets"][0]
    end = int(title["original_start"], 16) + title["korean_consumed_bytes"]
    old_end = int(title["original_start"], 16) + title["jp_consumed_bytes"]
    validate_reclaimed_suffix(end, old_end,
                              ((TITLE_VENEER_START, TITLE_VENEER_END),))
    adopted_starts = _table_starts(adopted_korean, ordered=False)
    if adopted_starts[9] != 0xC80000:
        raise ValueError("Diagnostic title relocation profile changed")
    direct = _direct_pointer_hits(adopted_korean, 0x37C09C, old_end)
    if direct:
        raise ValueError(f"Expanded diagnostic has source-title direct references: {direct}")
    return dict(start=TITLE_VENEER_START, end=TITLE_VENEER_END,
                bytes=TITLE_VENEER_END - TITLE_VENEER_START,
                jp_expected_bytes=japanese[TITLE_VENEER_START:TITLE_VENEER_END].hex(),
                diagnostic_expected_bytes=adopted_korean[TITLE_VENEER_START:TITLE_VENEER_END].hex(),
                jp_profile="install title resource #9 in-place first; compressed consumer stops before slot",
                diagnostic_profile="resource #9 relative table already points to C80000",
                direct_pointer_hits_in_jp=0, direct_pointer_hits_in_diagnostic=0,
                caller_0801C3B4_thumb_bl_reachable=(
                    abs(TITLE_VENEER_START - (0x1C3B4 + 4)) < 0x400000),
                remaining_gate="prove veneer instructions/caller ABI and runtime execution")


def plan_small_font(japanese: bytes, adopted_korean: bytes) -> tuple[Write, dict]:
    """Restore both native small-font pointers by placing Korean LZ in place."""
    if len(japanese) != ROM_SIZE or sha(japanese) != JP_SHA:
        raise ValueError("Japanese source identity mismatch")
    if len(adopted_korean) != 13270790 or sha(adopted_korean) != KO_SHA:
        raise ValueError("Adopted Korean source identity mismatch")
    source, jp_used = _lz(japanese, SMALL_FONT_START, 0x10000)
    target, ko_used = _lz(adopted_korean, SMALL_FONT_KO_START, 0x10000)
    if len(source) != len(target) or len(source) != 8192 or (jp_used, ko_used) != (1997, 1564):
        raise ValueError("Small-font geometry or compressed extents changed")
    if SMALL_FONT_START + jp_used > SMALL_FONT_RESERVED_END:
        raise ValueError("Original small-font stream exceeds reserved extent")
    for storage in (0x2158, 0x21D4):
        if struct.unpack_from("<I", japanese, storage)[0] != ROM_BASE + SMALL_FONT_START:
            raise ValueError("Original small-font pointer changed")
        if struct.unpack_from("<I", adopted_korean, storage)[0] != ROM_BASE + SMALL_FONT_KO_START:
            raise ValueError("Adopted small-font pointer changed")
    hits = _direct_pointer_hits(japanese, SMALL_FONT_START, SMALL_FONT_START + jp_used)
    if hits != [0x2158, 0x21D4]:
        raise ValueError(f"Unexpected original small-font interior reference: {hits}")
    payload = adopted_korean[SMALL_FONT_KO_START:SMALL_FONT_KO_START + ko_used]
    if _lz(payload, 0, 0x10000) != (target, ko_used):
        raise ValueError("Small-font stream extraction failed")
    write = Write("asset:small_korean_font", SMALL_FONT_START,
                  japanese[SMALL_FONT_START:SMALL_FONT_START + ko_used], payload,
                  "lossless Korean 8x8 LZ stream at original small-font address",
                  "native font pointers at 00002158 and 000021D4",
                  "exact adopted Korean font stream and AN9J source",
                  ("bounded_lz_decode", "pointer_pair", "reserved_boundary"))
    return write, dict(original_start=f"{SMALL_FONT_START:08X}",
                       original_consumed_bytes=jp_used, korean_consumed_bytes=ko_used,
                       reserved_end=f"{SMALL_FONT_RESERVED_END:08X}",
                       decoded_bytes=len(target), decoded_sha256=sha(target),
                       stream_sha256=sha(payload), direct_pointer_storages=hits,
                       pointer_values_unchanged=True,
                       caveat="Original ASCII staff font must be retained at a separate proven owner")


def plan_staff_font_relocation(japanese: bytes, adopted_korean: bytes) -> tuple[list[Write], dict]:
    """Retain the original ASCII font inside the reclaimed title #9 suffix.

    This supplies only the staff-page font consumer and its stream. The full
    ending credits extension has its own table/text ownership requirement.
    """
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
    from build_banked_font import assemble

    owner = title_veneer_owner(japanese, adopted_korean)
    old_wrapper = assemble(Path(__file__).resolve().parents[1] /
                           "asm/ending_original_font.s", 0xC86F00, 0, 0x80)
    if adopted_korean[0xC86F00:0xC86F00+len(old_wrapper)] != old_wrapper:
        raise ValueError("Adopted staff font wrapper changed")
    native_stream = japanese[SMALL_FONT_START:SMALL_FONT_START + 1997]
    if _lz(native_stream, 0, 0x10000)[0] != _lz(japanese, SMALL_FONT_START, 0x10000)[0]:
        raise ValueError("Native staff font copy is not self-contained")
    title_end = 0x37C09C + 6364
    old_title_end = 0x37C09C + 8913
    validate_reclaimed_suffix(title_end, old_title_end, (
        (owner["start"], owner["end"]),
        (STAFF_WRAPPER_START, STAFF_WRAPPER_START + len(old_wrapper)),
        (STAFF_FONT_START, STAFF_FONT_START + len(native_stream)),
    ))
    template = (Path(__file__).resolve().parents[1] /
                "asm/ending_original_font.s").read_text(encoding="utf-8")
    old_literal, new_literal = ".word 0x08C86000", f".word {ROM_BASE + STAFF_FONT_START:#010x}"
    if template.count(old_literal) != 1:
        raise ValueError("Staff wrapper font-stream relocation point changed")
    source = template.replace(old_literal, new_literal)
    wrapper = bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(
        source, addr=ROM_BASE + STAFF_WRAPPER_START)[0])
    if len(wrapper) != len(old_wrapper) or not wrapper.endswith(struct.pack("<I", 0x080A59D5)):
        raise ValueError("Relocated staff wrapper size or return changed")
    decoded = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(
        wrapper[:len(wrapper)-16], ROM_BASE + STAFF_WRAPPER_START))
    if not decoded or decoded[0].mnemonic != "push" or any(
            ins.mnemonic in ("blx", "it", "movw", "movt") for ins in decoded):
        raise ValueError("Relocated staff wrapper is not Thumb-1")
    if japanese[STAFF_HOOK_STORAGE:STAFF_HOOK_STORAGE + 8] != bytes.fromhex("00b503201e210022"):
        raise ValueError("Original staff-page hook owner changed")
    hook = bytes.fromhex("004b1847") + struct.pack("<I", ROM_BASE + STAFF_WRAPPER_START + 1)
    writes = [
        Write("asset:native_staff_font", STAFF_FONT_START,
              japanese[STAFF_FONT_START:STAFF_FONT_START+len(native_stream)], native_stream,
              "preserve original ASCII font stream after small-font replacement",
              "staff-page wrapper at original A59CC entry",
              "exact AN9J native font stream", ("bounded_lz_decode", "title_suffix_owner")),
        Write("asset:staff_font_wrapper", STAFF_WRAPPER_START,
              japanese[STAFF_WRAPPER_START:STAFF_WRAPPER_START+len(wrapper)], wrapper,
              "relocate native staff font wrapper using named font-stream symbol",
              "original staff-page entry A59CC",
              "exact adopted wrapper and AN9J title suffix", ("thumb1", "source_wrapper_match")),
        Write("asset:staff_font_entry", STAFF_HOOK_STORAGE,
              japanese[STAFF_HOOK_STORAGE:STAFF_HOOK_STORAGE+8], hook,
              "branch to relocated staff-page font wrapper",
              "staff-page entry A59CC and native return A59D5",
              "established adopted hook encoding with relocated Thumb pointer",
              ("expected_instruction", "thumb_pointer", "return_target")),
    ]
    return writes, dict(wrapper_start=f"{STAFF_WRAPPER_START:08X}",
                        wrapper_bytes=len(wrapper), font_start=f"{STAFF_FONT_START:08X}",
                        font_bytes=len(native_stream), font_sha256=sha(native_stream),
                        hook_storage=f"{STAFF_HOOK_STORAGE:08X}", hook_after=hook.hex(),
                        suffix_end=f"{old_title_end:08X}",
                        caveat="credits table/text still requires independent in-ROM allocation")


def plan_credits_relocation(japanese: bytes, adopted_korean: bytes) -> tuple[list[Write], dict]:
    """Move final 199-row credits table/text into retired copyright RL suffix."""
    _, title_plan = plan_title_assets(japanese, adopted_korean)
    copyright_row = title_plan["assets"][1]
    new_end = int(copyright_row["original_start"], 16) + copyright_row["korean_consumed_bytes"]
    old_end = int(copyright_row["original_start"], 16) + copyright_row["jp_consumed_bytes"]
    validate_reclaimed_suffix(new_end, old_end,
                              ((CREDITS_START, CREDITS_START + CREDITS_LENGTH),))
    if _direct_pointer_hits(adopted_korean, 0x37EBE8, old_end):
        raise ValueError("Expanded diagnostic has old copyright-stream references")
    if struct.unpack_from("<I", japanese, 0xA56E8)[0] != ROM_BASE + 0x7F9608:
        raise ValueError("Japanese staff-table pointer changed")
    if struct.unpack_from("<I", adopted_korean, 0xA56E8)[0] != ROM_BASE + CREDITS_OLD_START:
        raise ValueError("Adopted staff-table pointer changed")
    payload = bytearray(adopted_korean[CREDITS_OLD_START:CREDITS_OLD_START+CREDITS_LENGTH])
    if len(payload) != CREDITS_LENGTH or payload[:191*4] != japanese[0x7F9608:0x7F9904]:
        raise ValueError("Original 191 staff rows not preserved")
    if struct.unpack_from("<I", payload, 199*4)[0] != 0:
        raise ValueError("Final staff table terminator changed")
    relocated = 0
    for index in range(199):
        value = struct.unpack_from("<I", payload, index*4)[0]
        if ROM_BASE + CREDITS_OLD_START <= value < ROM_BASE + CREDITS_OLD_START+CREDITS_LENGTH:
            at = value - ROM_BASE - CREDITS_OLD_START
            if at < 200*4 or b"\0" not in payload[at:]:
                raise ValueError("Appended credits string does not terminate in payload")
            struct.pack_into("<I", payload, index*4, ROM_BASE + CREDITS_START + at)
            relocated += 1
        elif index >= 191 and not ROM_BASE <= value < ROM_BASE + len(japanese):
            raise ValueError("Unexpected external staff-row target")
    if relocated != 7:
        raise ValueError("Appended credits pointer population changed")
    if japanese[0xA5316:0xA5318] != bytes.fromhex("3521") or adopted_korean[0xA5316:0xA5318] != bytes.fromhex("3d21"):
        raise ValueError("Final staff scroll-count instruction changed")
    writes = [
        Write("asset:credits_table_and_strings", CREDITS_START,
              japanese[CREDITS_START:CREDITS_START+CREDITS_LENGTH], bytes(payload),
              "preserve original 191 rows and final eight translated credits rows",
              "staff table pointer at A56E8; seven relocated internal strings",
              "exact adopted credits payload with symbolic base relocation",
              ("row_population", "internal_pointer_bounds", "copyright_suffix_owner")),
        Write("asset:credits_table_pointer", 0xA56E8,
              japanese[0xA56E8:0xA56EC], struct.pack("<I", ROM_BASE + CREDITS_START),
              "point staff renderer at final in-ROM table",
              "staff renderer's original pointer literal at A56E8",
              "exact AN9J literal and adopted credits table",
              ("original_191_rows", "table_terminator")),
        Write("asset:credits_scroll_rows", 0xA5316,
              japanese[0xA5316:0xA5318], bytes.fromhex("3d21"),
              "retain eight appended ending rows in scroll limit",
              "original ending scroll loop at A5316",
              "exact adopted credits instruction", ("expected_instruction",)),
    ]
    return writes, dict(table_start=f"{CREDITS_START:08X}", payload_bytes=len(payload),
                        table_rows=199, original_rows=191, appended_rows=8,
                        relocated_string_pointers=relocated,
                        copyright_lz_end=f"{new_end:08X}",
                        original_copyright_stream_end=f"{old_end:08X}",
                        old_stream_absolute_pointer_hits_in_diagnostic=0,
                        relocated_payload_sha256=sha(payload),
                        remaining_gate="actual ending renderer and final 8MiB product execution")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--japanese", type=Path, required=True)
    parser.add_argument("--adopted", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Choose a new output folder")
    jp, ko = args.japanese.read_bytes(), args.adopted.read_bytes()
    writes, report = plan_title_assets(jp, ko)
    font_write, font_report = plan_small_font(jp, ko)
    writes.append(font_write)
    staff_writes, staff_report = plan_staff_font_relocation(jp, ko)
    writes.extend(staff_writes)
    credits_writes, credits_report = plan_credits_relocation(jp, ko)
    writes.extend(credits_writes)
    report["small_font"] = font_report
    report["staff_font_relocation"] = staff_report
    report["credits_relocation"] = credits_report
    report["all_planned_bytes"] = sum(len(write.after) for write in writes)
    report["near_veneer_owner"] = title_veneer_owner(jp, ko)
    args.out.mkdir(parents=True)
    for write in writes:
        (args.out / f"{write.writer_id.replace(':', '_')}.bin").write_bytes(write.after)
    report["writes"] = [write.manifest() for write in writes]
    (args.out / "TITLE_ASSET_PLAN.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()

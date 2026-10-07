"""Guarded eight-MiB *diagnostic* link of the frozen strict-layout probes.

This deliberately retains an OPEN ledger for adopted lower-ROM changes whose
individual game consumers have not been closed.  It is never a release build.
No byte after the Japanese cartridge boundary is copied by slicing/truncation.
"""
from __future__ import annotations

import argparse
import csv
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT
sys.path.insert(1, str(SOURCE / "tools"))

from strict_layout_core import ROM_BASE, ROM_SIZE, sha
from strict_asset_fontrows8 import ARENA_START, FONT_END, plan_font_rows8
from strict_asset_writeplan import (plan_title_assets, plan_small_font,
    plan_staff_font_relocation, plan_credits_relocation)

JP_SHA = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
KO_SHA = "eac45b3345e865f1fea68bbb07f62aff0f6ccdf03004090f57b55f75b6f82b73"
PROBE_SHA = "75bcd99c2c517646a59dacd1af8219e11a130f26070fdaf1d141cec0f8c32d3b"
GUARDED_PROBE_SHA = "c70c5ec1ab0964ea4e44010790917cc616027b6b318caf0050afe10694a3ef22"
TITLE_UNIT = 0x37E1F0
TITLE_UNIT_LIMIT = 0x37E36D
BUILD_DIR = SOURCE / "private_validation/v11-runtime-20261003/owned-all-extra-a"
INLINE_DIR = SOURCE / "private_validation/strict-layout-20261003/build-inline-native-a"


def align(value: int, modulus: int = 4) -> int:
    if modulus < 1 or modulus & (modulus - 1):
        raise ValueError("Alignment must be a power of two")
    return (value + modulus - 1) & -modulus


@dataclass(frozen=True)
class Segment:
    name: str
    old: int
    new: int
    size: int
    kind: str

    @property
    def end(self) -> int:
        return self.new + self.size


def read_inputs(japanese: Path, adopted: Path, probe: Path, build: Path):
    jp, ko, diagnostic = japanese.read_bytes(), adopted.read_bytes(), probe.read_bytes()
    if len(jp) != ROM_SIZE or sha(jp) != JP_SHA:
        raise ValueError("Exact Japanese 8 MiB source required")
    if len(ko) != 13270790 or sha(ko) != KO_SHA:
        raise ValueError("Exact adopted Korean source required")
    diagnostic_sha=sha(diagnostic)
    if diagnostic_sha not in (PROBE_SHA,GUARDED_PROBE_SHA):
        raise ValueError("Exact frozen alias diagnostic required")
    report = json.loads(build.read_text(encoding="utf-8"))
    if (report.get("sha256") != diagnostic_sha or report.get("bindings") != 10172
            or report.get("unique_starts") != 9246 or not report.get("aliases")):
        raise ValueError("Diagnostic manifest denominator changed")
    return jp, ko, diagnostic, report


def component_table(manifest: dict) -> list[tuple[str, int, int, str]]:
    """Exact frozen source spans; zero-filled gaps are never allocation proof."""
    rows = []
    for row in manifest["writes"]:
        old, end = row["start"], row["end"]
        if old < 0xC90000:
            continue
        name = row["writer_id"].split(":", 1)[1]
        kind = ("stream" if name == "boot_notice_1bpp_pixels" else
                "data" if name in {"full_book", "compact_book", "full_bounds",
                    "compact_bounds", "extra_book", "extra_bounds", "aliases", "select_descriptors"} else "code")
        rows.append((name, old, end - old, kind))
    if len(rows) != 32:
        raise ValueError("Generic component inventory changed")
    # These adopted components have exact build-chain source identities.  Only
    # the named source extents are copied; the rest of C0/C1 remains unowned.
    native = (
        ("compact_get_tile", 0xC00600, 100),
        ("banked_small", 0xC00000, 80),
        ("banked_simple", 0xC00100, 72),
        ("banked_full_name", 0xC00200, 76),
        ("banked_convert", 0xC00300, 68),
        ("banked_decode", 0xC00500, 52),
        ("banked_popup", 0xC00C00, 212),
        ("banked_name_import", 0xC01000, 156),
        ("banked_name_commit", 0xC01200, 28),
        ("banked_actor_name_resolve", 0xC1E880, 52),
        ("banked_actor_monster_init", 0xC1E900, 36),
        ("banked_actor_party_init", 0xC1E980, 36),
        ("banked_actor_small_entry", 0xC1EA00, 40),
        ("banked_actor_format_string", 0xC1EA80, 44),
        ("banked_battle_font_upload", 0xC1EB00, 48),
        ("banked_inspect_text", 0xC1EC00, 232),
        ("tile_cache", 0xC00800, 680),
        ("legacy_failstop", 0xC00700, 2),
        ("large_codes", 0xC0A000, 1024),
        ("clear_font", 0xC02000, 16384),
    )
    rows.extend((name, old, size, "generated" if name == "compact_get_tile" else
                 "data" if name in {"large_codes", "clear_font"} else "code")
                for name, old, size in native)
    return rows


def plan_segments(manifest: dict) -> tuple[list[Segment], dict]:
    components = component_table(manifest)
    old_offsets = {name: old for name, old, _, _ in components}
    if len(old_offsets) != len(components):
        raise ValueError("Duplicate component name")
    segments = []
    cursor = ARENA_START
    for name, old, size, kind in components:
        if name == "unit":
            new = TITLE_UNIT
            if new + size > TITLE_UNIT_LIMIT:
                raise ValueError("Unit decoder exceeds audited retired title suffix")
        else:
            cursor = align(cursor, 4)
            new = cursor
            cursor += size
        segments.append(Segment(name, old, new, size, kind))
    if cursor > FONT_END:
        raise ValueError(f"Font-owner arena overflow: {cursor - FONT_END} bytes")
    for a, b in zip(sorted(segments, key=lambda s: s.new),
                    sorted(segments, key=lambda s: s.new)[1:]):
        if a.end > b.new:
            raise ValueError(f"Allocated overlap: {a.name}, {b.name}")
    summary = dict(arena=[ARENA_START, FONT_END], used=cursor - ARENA_START,
                   free=FONT_END - cursor, title_unit=[TITLE_UNIT, TITLE_UNIT + 326],
                   segments=[dict(name=s.name, old=s.old, new=s.new, size=s.size,
                                  end=s.end, kind=s.kind) for s in segments])
    return segments, summary


def relocate_address(value: int, segments: list[Segment]) -> int | None:
    # Original adopted entry shims are replaced by the exact generic wrappers.
    # Their old ROM pointers may still occur in adopted native hook veneers.
    alias = {0xC01400: "banked_name_init_first_new",
             0xC01480: "banked_name_init_second_new",
             0xC1E800: "actor_store"}
    for old, destination in alias.items():
        if value in (ROM_BASE + old, ROM_BASE + old + 1):
            target = next(s for s in segments if s.name == destination)
            return ROM_BASE + target.new + (value & 1)
    for part in segments:
        if ROM_BASE + part.old <= value < ROM_BASE + part.old + part.size:
            return ROM_BASE + part.new + value - (ROM_BASE + part.old)
    return None


def relocate_code_literals(source: bytes, part: Segment, segments: list[Segment]):
    """Relocate only aligned literal words with a named source component."""
    data = bytearray(source)
    # All linked components are Thumb code with PC-relative literal pools.
    # Two valid instruction halfwords can resemble an expanded address (the
    # boot pixel loop includes 0x09053402). They are not data relocations.
    literal_targets = set()
    for offset in range(0,len(data)-1,2):
        half = struct.unpack_from('<H',data,offset)[0]
        if half & 0xF800 == 0x4800:
            target = ((part.old+offset+4)&~3)+(half&255)*4-part.old
            if offset < target <= len(data)-4:
                literal_targets.add(target)
    first_literal = min(literal_targets,default=0)
    relocated = []
    unresolved = []
    for pos in range(0, len(data) - 3, 4):
        value = struct.unpack_from("<I", data, pos)[0]
        if not (0x08800000 <= value < 0x0A000000):
            continue
        if pos < first_literal and pos not in literal_targets:
            continue
        target = relocate_address(value, segments)
        if target is None:
            unresolved.append(dict(component=part.name, at=pos, value=value))
            continue
        struct.pack_into("<I", data, pos, target)
        relocated.append(dict(component=part.name, at=pos, old=value, new=target))
    return bytes(data), relocated, unresolved


def scan_changed_expanded_refs(japanese: bytes, image: bytes, segments: list[Segment]):
    """List changed aligned words; never infer ownership from equal JP bytes."""
    matched, unresolved = [], []
    for at in range(0, ROM_SIZE, 4):
        if image[at:at+4] == japanese[at:at+4]:
            continue
        value = struct.unpack_from("<I", image, at)[0]
        if not 0x08800000 <= value < 0x0A000000:
            continue
        mapped = relocate_address(value, segments)
        record = dict(at=at, value=value)
        if mapped is None:
            unresolved.append(record)
        else:
            record["relocated"] = mapped
            matched.append(record)
    return matched, unresolved


class Ledger:
    def __init__(self, japanese: bytes):
        self.image = bytearray(japanese)
        self.entries = []
        self.owner = bytearray(ROM_SIZE)  # source, probe, final allocation stages

    def put(self, name: str, at: int, expected: bytes, after: bytes,
            *, stage: int, evidence: str):
        if not after or len(expected) != len(after) or not 0 <= at <= ROM_SIZE - len(after):
            raise ValueError(name + ": invalid extent")
        if self.image[at:at+len(after)] != expected:
            raise ValueError(name + ": expected-source guard failed")
        old_stage = self.owner[at:at+len(after)]
        if any(previous > stage for previous in old_stage):
            raise ValueError(name + ": backwards stage override")
        if any(previous == stage for previous in old_stage):
            raise ValueError(name + ": same-stage owner collision")
        self.image[at:at+len(after)] = after
        self.owner[at:at+len(after)] = bytes([stage])*len(after)
        self.entries.append(dict(name=name, start=at, end=at+len(after),
            stage=stage, before_sha256=sha(expected), after_sha256=sha(after),
            evidence=evidence))


def adopted_carryovers(ledger: Ledger, japanese: bytes, adopted: bytes):
    """Explicitly guarded OPEN provenance; never claim source-consumer closure."""
    start = None
    for i in range(ROM_SIZE + 1):
        differs = i < ROM_SIZE and japanese[i] != adopted[i]
        if differs and start is None:
            start = i
        if not differs and start is not None:
            ledger.put(f"adopted_carryover_open:{start:06x}", start,
                       japanese[start:i], adopted[start:i], stage=1,
                       evidence="exact adopted lower-ROM byte; individual owner/consumer OPEN")
            start = None


def generic_probe_writes(ledger: Ledger, adopted: bytes, diagnostic: bytes, manifest: dict):
    count = 0
    for row in manifest["writes"]:
        start, end = row["start"], row["end"]
        if end > ROM_SIZE:
            continue
        original = adopted[start:end]
        target = diagnostic[start:end]
        if sha(original) != row["before_sha256"] or sha(target) != row["after_sha256"]:
            raise ValueError("Frozen generic write hash mismatch: " + row["writer_id"])
        ledger.put(row["writer_id"], start, original, target, stage=2,
                   evidence="frozen generic diagnostic manifest; consumer closure OPEN")
        count += 1
    return count


def replace(ledger: Ledger, name: str, at: int, after: bytes, evidence: str):
    ledger.put(name, at, bytes(ledger.image[at:at+len(after)]), after,
               stage=3, evidence=evidence)


def exact_asset_writes(ledger: Ledger, japanese: bytes, adopted: bytes):
    from strict_relative_assets import plan as plan_relative_assets
    from strict_map_assets import plan as plan_map_assets
    title, _ = plan_title_assets(japanese, adopted)
    small, _ = plan_small_font(japanese, adopted)
    staff, _ = plan_staff_font_relocation(japanese, adopted)
    credits, _ = plan_credits_relocation(japanese, adopted)
    font, font_report = plan_font_rows8(japanese, adopted)
    relative, relative_report = plan_relative_assets(japanese, adopted)
    maps, maps_report = plan_map_assets(japanese, adopted)
    font_report['map_assets'] = maps_report
    font_report['relative_assets'] = relative_report
    rows = title + [small] + staff + credits + font + relative + maps
    for row in rows:
        if japanese[row.start:row.end] != row.before:
            raise ValueError(row.writer_id + ": original asset guard changed")
        replace(ledger, row.writer_id, row.start, row.after,
                row.purpose + "; " + row.provenance)
    # The title resource table stores relative offsets rather than absolute
    # pointers.  The in-place lossless streams require the original entries.
    for at in (0x376920, 0x37693C):
        replace(ledger, f"asset:title_relative_table_{at:06x}", at,
                japanese[at:at+4], "bounded in-place title/copyright stream owner")
    for at in (0x2158, 0x21D4):
        replace(ledger, f"asset:small_font_literal_{at:06x}", at,
                japanese[at:at+4], "native small-font LZ stream restored in place")
    # Stable original 8-byte CpuSet signature is a save compatibility invariant.
    if japanese[0x2BF4C8:0x2BF4D0] != b"NARIKIRI":
        raise ValueError("Original save signature changed")
    replace(ledger, "save:signature_source", 0xA1E4, japanese[0xA1E4:0xA1E8],
            "same original aligned NARIKIRI source for CpuSet and cold load")
    return len(rows), font_report


def relocate_components(ledger: Ledger, adopted: bytes, probe: bytes,
                        manifest: dict, segments: list[Segment]):
    from strict_compact_font_clear import assemble as assemble_get_tile
    from strict_compact_font_clear import validate_banks
    from build_banked_font import assemble as assemble_adopted
    old_by_name = {r["writer_id"].split(":", 1)[1]: r
                   for r in manifest["writes"] if r["start"] >= 0xC90000}
    by_name = {part.name: part for part in segments}
    validate_banks(adopted[0xC02000:0xC06000], adopted[0xC06000:0xC0A000])
    literal_fixes, unresolved_literals = [], []
    for part in segments:
        if part.name == "compact_get_tile":
            data = assemble_get_tile(ROM_BASE + part.new,
                decoder=ROM_BASE + by_name["banked_decode"].new + 1,
                cache=ROM_BASE + by_name["tile_cache"].new + 1,
                clear_font=ROM_BASE + by_name["clear_font"].new)
            if len(data) != part.size:
                raise ValueError("Compact clear getter size changed")
        else:
            origin = probe if part.old >= 0xC90000 else adopted
            data = origin[part.old:part.old+part.size]
            if len(data) != part.size:
                raise ValueError(part.name + ": missing source")
            if part.old >= 0xC90000:
                record = old_by_name[part.name]
                if sha(data) != record["after_sha256"]:
                    raise ValueError(part.name + ": frozen component hash mismatch")
            elif part.name.startswith("banked_"):
                source = SOURCE / "asm" / (part.name + ".s")
                expected = assemble_adopted(source, part.old, 512, 512)
                if len(expected) != part.size or data != expected:
                    raise ValueError(part.name + ": adopted source and ROM differ")
            elif part.name == "tile_cache":
                source = SOURCE / "asm/private_tile_cache_listperf_pass01.s"
                expected = assemble_adopted(source, part.old, 512, 1024)
                if len(expected) != part.size or data != expected:
                    raise ValueError("Frozen list performance cache differs")
            if part.kind == "code":
                data, changed, unresolved = relocate_code_literals(data, part, segments)
                literal_fixes.extend(changed)
                unresolved_literals.extend(unresolved)
        if part.name == "boot_notice_1bpp_wrapper":
            # The original LZ pointer appears once in the literal pool; other
            # boot state and pixel LUT bytes must remain exact.
            original = struct.pack("<I", ROM_BASE + 0xC91000)
            target = struct.pack("<I", ROM_BASE + by_name["boot_notice_1bpp_pixels"].new)
            if data.count(original) == 1:
                data = data.replace(original, target)
        replace(ledger, "relocated:" + part.name, part.new, data,
                "named source span and guarded reclaimed full-font/title owner")
    if unresolved_literals:
        raise ValueError("Unmapped expanded code literals: " + repr(unresolved_literals[:20]))
    return literal_fixes


def repoint_known_hooks(ledger: Ledger, japanese: bytes, segments: list[Segment]):
    """Only changed words with a mapped exact component target are candidates.

    Native entry veneers are structurally recognized; unknown pointer-shaped
    changed data remains OPEN in the report rather than silently rewritten.
    """
    matched, unresolved = scan_changed_expanded_refs(japanese, ledger.image, segments)
    patched, suspicious = [], []
    # Non-veneer words below have separately identified instruction/data
    # consumers: boot vector, small/simple font helper literal pools, event
    # high-register trampoline and SELECT_JOB's audited title relay.
    direct = {0x100, 0x1AF4, 0x1E14, 0x9896C, 0x37D98C, 0x37E1BC}
    for hit in matched:
        at = hit["at"]
        # Thumb direct veneers are exactly LDR r3,[pc] ; BX r3 ; literal.
        # Ordinary words in source binary remain unresolved until classified.
        if at in direct or (at >= 4 and
                            ledger.image[at-4:at] == b"\x00\x4b\x18\x47"):
            replace(ledger, f"hook:veneer_{at:06x}", at,
                    struct.pack("<I", hit["relocated"]),
                    "identified boot vector, instruction literal, or exact Thumb entry veneer")
            patched.append(hit)
        else:
            suspicious.append(hit)
    return patched, suspicious, unresolved


def annotate_pointer_shapes(ledger: Ledger, japanese: bytes, refs: list[dict], adopted=None):
    """Attach final byte owner; an encoded byte run is not a live ROM pointer."""
    result = []
    from strict_reference_audit import preserved_graphic_owners,extra_classification
    owners=preserved_graphic_owners(japanese,adopted,ledger.image) if adopted is not None else []
    for row in refs:
        at = row["at"]
        writer = next((w for w in reversed(ledger.entries)
                       if w["start"] < at + 4 and at < w["end"]), None)
        name = writer["name"] if writer else "unchanged_japanese"
        complete=writer and writer['start']<=at and at+4<=writer['end']
        kind = ("encoded_payload_pointer_shape" if complete and name.startswith((
            "owned_probe:stream_", "asset:font_rows8", "asset:title_resource_",
            "asset:small_korean_font", "relocated:boot_notice_1bpp_pixels",
            "relocated:full_book", "relocated:compact_book",
            "relocated:full_bounds", "relocated:compact_bounds",
            "relocated:extra_book", "relocated:extra_bounds", "owned_probe:extra_ui_stream_",
            "asset:native_row_decoder", "asset:relative_")) else "unclassified_changed_reference")
        proof=extra_classification(japanese,adopted,ledger.image,owners,at,writer) if adopted is not None else None
        if proof:kind=proof['kind']
        result.append(dict(row, owner=name, classification=kind,proof=proof,
                           japanese_word=struct.unpack_from("<I", japanese, at)[0]))
    return result


def verify_binding_storage(image: bytes, japanese: bytes, csv_path: Path):
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 10172 or len({int(r["jp_text_start"]) for r in rows}) != 9246:
        raise ValueError("Frozen binding denominator changed")
    for row in rows:
        at, start = int(row["jp_pointer_storage"]), int(row["jp_text_start"])
        if image[at:at+4] != japanese[at:at+4]:
            raise ValueError("Protected pointer changed: " + row.get("id", str(at)))
        if struct.unpack_from("<I", image, at)[0] != ROM_BASE + start:
            raise ValueError("Text start no longer matches pointer")
    for at in (0x9780, 0x9788):
        if image[at:at+4] != japanese[at:at+4]:
            raise ValueError("Extra fixed-name pointer changed")
    return dict(bindings=10172, starts=9246, extra_fixed_names=2,
                pointer_mismatch=0)


def install_owned_menus(ledger, japanese, manifest, segments, plan, inline_dir=INLINE_DIR):
    from strict_menu_owned import (verify_tables, verify_dynamic_source,
        descriptor_bytes, assemble_wrapper, assemble_trampoline, assemble_entry_patch)
    def rows(name):
        with (inline_dir/name).open(encoding='utf-8-sig',newline='') as f:
            return list(csv.DictReader(f))
    historical,fits=rows('TEXT_BINDINGS.csv'),rows('SLOT_FIT_REPORT.csv')
    before=bytes(ledger.image)
    static=verify_tables(japanese,before,historical,fits,manifest['extra_ui']['rows'])
    dynamic=verify_dynamic_source(japanese,before,historical,fits)
    start=align(ARENA_START+plan['used'])
    descriptors=descriptor_bytes()
    code=assemble_wrapper(ROM_BASE+start,descriptor_address=ROM_BASE+start+268,
        decoder=ROM_BASE+next(s.new for s in segments if s.name=='owned')+1,
        original_menu=ROM_BASE+start+316+1)
    trampoline=assemble_trampoline(ROM_BASE+start+316,japanese)
    payload=code+descriptors+trampoline
    if (len(code),len(descriptors),len(trampoline))!=(268,48,24) or start+len(payload)>FONT_END:
        raise ValueError('Owned menu arena contract')
    replace(ledger,'menu:owned_adapter',start,payload,'bounded menu heap lives through blocking native call')
    replace(ledger,'menu:entry',0x4D98,assemble_entry_patch(ROM_BASE+start+1),'exact native entry prologue preserved by trampoline')
    return dict(start=start,end=start+len(payload),bytes=len(payload),
        free=FONT_END-start-len(payload),static=static,dynamic=dynamic,
        qualification='CPU/source contracts only; natural runtime validation separate')


def verify_frozen_streams(image: bytes, fits_path: Path, slot_image_path: Path,
                          book_dir: Path):
    """Re-read every in-place stream and all selected native values.

    The validator uses the frozen uncompressed dictionary solely as an
    independent oracle.  The linked runtime uses the exact v2 packed version.
    """
    from strict_unit_codec import decode_parts
    frozen = slot_image_path.read_bytes()
    if len(frozen) < ROM_SIZE:
        raise ValueError("Frozen slot image is incomplete")
    books = {kind: (book_dir / f"EXPERIMENT_CODEBOOK_{kind}.bin").read_bytes()
             for kind in ("full_text", "compact")}
    with fits_path.open(encoding="utf-8-sig", newline="") as f:
        fits = list(csv.DictReader(f))
    if len(fits) != 10172:
        raise ValueError("Frozen fit denominator changed")
    for row in fits:
        start = int(row["jp_text_start"])
        length = int(row["encoded_length"])
        capacity = int(row["slot_capacity"])
        if not (0 < length <= capacity and start + capacity <= ROM_SIZE):
            raise ValueError("Frozen slot extent changed")
        if image[start:start+length] != frozen[start:start+length]:
            raise ValueError(row["binding_id"] + ": encoded stream differs")
        if sha(image[start:start+length]) != row["stream_sha256"]:
            raise ValueError(row["binding_id"] + ": encoded stream hash differs")
        native, used = decode_parts(image[start:start+capacity],
            books[row["category"]], int(row["native_output_length"]),
            int(row["inline_part_count"]), int(row["inline_selection"]),
            allow_suffix=True)
        if used != length or sha(native) != row["native_output_sha256"]:
            raise ValueError(row["binding_id"] + ": native value differs")
    return dict(frozen_occurrences=len(fits), native_value_mismatch=0,
                stream_byte_mismatch=0,
                qualification="content and start only; runtime consumer closure OPEN")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--japanese", type=Path, required=True)
    parser.add_argument("--adopted", type=Path, required=True)
    parser.add_argument("--probe", type=Path, default=BUILD_DIR / "OWNED_ALL_STREAMS_DIAGNOSTIC_NOT_PRODUCT.gba")
    parser.add_argument("--build", type=Path, default=BUILD_DIR / "BUILD.json")
    parser.add_argument("--text-build", type=Path, default=INLINE_DIR)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--owned-menus", action="store_true")
    parser.add_argument("--fast-full-draw", action="store_true")
    parser.add_argument("--direct-dialogue", action="store_true")
    parser.add_argument("--arte-description-length", action="store_true")
    args = parser.parse_args()
    jp, ko, probe, manifest = read_inputs(args.japanese, args.adopted, args.probe, args.build)
    segments, plan = plan_segments(manifest)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "LAYOUT.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    if args.plan_only:
        print(json.dumps({"used": plan["used"], "free": plan["free"]}))
        return
    ledger = Ledger(jp)
    adopted_carryovers(ledger, jp, ko)
    generic_count = generic_probe_writes(ledger, ko, probe, manifest)
    asset_count, font_report = exact_asset_writes(ledger, jp, ko)
    code_literals = relocate_components(ledger, ko, probe, manifest, segments)
    menu_report=install_owned_menus(ledger,jp,manifest,segments,plan,args.text_build) if args.owned_menus else None
    patched, suspicious, unresolved = repoint_known_hooks(ledger, jp, segments)
    draw_report=None
    if args.fast_full_draw:
        from strict_perf_full_draw_fast_8m import build as build_fast_draw
        optimized,draw_report=build_fast_draw(bytes(ledger.image))
        for write in draw_report['writes']:
            at=int(write['offset'],16);end=at+write['size']
            replace(ledger,'performance:'+write['name'],at,optimized[at:end],
                'guarded retired font owner or native full-font callsite')
        if bytes(ledger.image)!=optimized:raise ValueError('Fast draw write plan differs')
    dialogue_report=None
    if args.direct_dialogue:
        from strict_direct_dialogue import diagnostic_patch
        decoded,dialogue_report=diagnostic_patch(jp,bytes(ledger.image))
        for write in dialogue_report['writes']:
            at=write['offset'];end=at+write['bytes']
            replace(ledger,'direct_dialogue:'+hex(at),at,decoded[at:end],
                'exact input profile; synchronous native dialogue with caller-owned decoded buffer')
        if bytes(ledger.image)!=decoded:raise ValueError('Direct dialogue write plan differs')
    length_report=None
    if args.arte_description_length:
        from strict_arte_desc_length import diagnostic_patch as patch_description_length
        decoded,length_report=patch_description_length(jp,bytes(ledger.image))
        for write in length_report['writes']:
            at=write['offset'];end=at+write['bytes']
            replace(ledger,'arte_description_length:'+hex(at),at,decoded[at:end],
                'decoded native byte length before original description layout branch')
        if bytes(ledger.image)!=decoded:raise ValueError('Description length write plan differs')
    suspicious = annotate_pointer_shapes(ledger, jp, suspicious, ko)
    unresolved = annotate_pointer_shapes(ledger, jp, unresolved, ko)
    if not all(0 <= s.new < s.end <= ROM_SIZE for s in segments):
        raise ValueError("Segment escaped the Japanese cartridge boundary")
    bindings = verify_binding_storage(ledger.image, jp,
                                      args.text_build / "TEXT_BINDINGS.csv")
    stream_check = verify_frozen_streams(ledger.image,
        args.text_build / "SLOT_FIT_REPORT.csv",
        args.text_build / "TEXT_SLOT_IMAGE_NOT_PLAYABLE.bin", args.text_build)
    result = bytes(ledger.image)
    if len(result) != ROM_SIZE or result[0x2BF4C8:0x2BF4D0] != b"NARIKIRI":
        raise ValueError("Fixed image size/save signature changed")
    report = dict(status="FIXED_8MIB_DISCOVERY_DIAGNOSTIC_NOT_PRODUCT",
        release_eligible=False, source_sha256=sha(jp), adopted_sha256=sha(ko),
        probe_sha256=sha(probe), output_sha256=sha(result), output_bytes=len(result),
        layout=plan, guarded_adopted_carryovers=sum(e["stage"] == 1 for e in ledger.entries),
        generic_writes=generic_count, asset_writes=asset_count,
        code_literal_relocations=code_literals, hook_veneer_relocations=patched,
        mapped_nonveneer_refs_open=suspicious,
        changed_expanded_refs_open=unresolved, protected_bindings=bindings,
        frozen_streams=stream_check,
        fast_full_draw=draw_report,
        direct_dialogue=dialogue_report,
        arte_description_length=length_report,
        font_profile=font_report.get("status"), asset_details=font_report, owned_menus=menu_report,
        remaining_gates=["lower-ROM carryover owner/consumer closure",
                         "unclassified expanded-reference closure",
                         "actual ARM7TDMI native decoded-value differential on final image",
                         "8-MiB runtime/save/performance regression"],
        writes=ledger.entries)
    (args.out / "FIXED_8MIB_DIAGNOSTIC_NOT_PRODUCT.gba").write_bytes(result)
    (args.out / "LINK.json").write_text(json.dumps(report, indent=2) + "\n",
                                        encoding="utf-8")
    with (args.out / "OPEN_REFERENCE_AUDIT.csv").open("w", newline="",
        encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(("storage_hex", "jp_word_hex", "adopted_word_hex",
                         "classification", "final_owner"))
        for row in unresolved + suspicious:
            writer.writerow((f"{row['at']:06X}", f"{row['japanese_word']:08X}",
                             f"{row['value']:08X}", row["classification"],
                             row["owner"]))
    print(json.dumps({key: report[key] for key in
        ("status", "output_bytes", "output_sha256", "guarded_adopted_carryovers",
         "generic_writes", "asset_writes")}))


if __name__ == "__main__":
    main()

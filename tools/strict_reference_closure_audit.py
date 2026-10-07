"""Bounded, independent reference check for the exact 8 MiB v1.1 diagnostic.

This does not infer reachability from address-shaped data and does not claim
complete consumer closure. It checks the contracts the linker census omits:
unaligned words, PC-relative loads/branches, signed relative tables and hooks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs


JP_SHA = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
ADOPTED_SHA = "eac45b3345e865f1fea68bbb07f62aff0f6ccdf03004090f57b55f75b6f82b73"
PROBE_SHA = "75bcd99c2c517646a59dacd1af8219e11a130f26070fdaf1d141cec0f8c32d3b"
ROM_SHA = "7105161a1d81c8e445265163c786880d66a79dacfb1f214e358313ef6b6c5916"
ROM_BASE = 0x08000000
DIRECT_HOOKS = {0x100, 0x1AF4, 0x1E14, 0x9896C, 0x37D98C, 0x37E1BC}
ENCODED_OWNERS = ("relocated:full_book", "relocated:full_bounds",
                  "relocated:compact_bounds", "owned_probe:stream_")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def word(data: bytes, at: int) -> int:
    return struct.unpack_from("<I", data, at)[0]


def source_bytes(path: Path, expected: str, length: int | None = None) -> bytes:
    data = path.read_bytes()
    if sha(data) != expected or (length is not None and len(data) != length):
        raise ValueError(f"Exact source identity changed: {path}")
    return data


def run(args: argparse.Namespace) -> dict:
    jp = source_bytes(args.japanese, JP_SHA, 0x800000)
    adopted = source_bytes(args.adopted, ADOPTED_SHA)
    probe = source_bytes(args.probe, PROBE_SHA)
    rom = source_bytes(args.rom, ROM_SHA, 0x800000)
    link = json.loads(args.link.read_text(encoding="utf-8"))
    if link["output_sha256"] != ROM_SHA or len(link["layout"]["segments"]) != 52:
        raise ValueError("Wrong linked report or segment inventory")
    parts = link["layout"]["segments"]
    by_name = {p["name"]: p for p in parts}

    def mapped(value: int) -> int | None:
        alias = {0xC01400: "banked_name_init_first_new",
                 0xC01480: "banked_name_init_second_new",
                 0xC1E800: "actor_store"}
        for old, name in alias.items():
            if value in (ROM_BASE + old, ROM_BASE + old + 1):
                return ROM_BASE + by_name[name]["new"] + (value & 1)
        offset = value - ROM_BASE
        for p in parts:
            if p["old"] <= offset < p["old"] + p["size"]:
                return ROM_BASE + p["new"] + offset - p["old"]
        return None

    fixed = {(r["component"], r["at"]): r for r in link["code_literal_relocations"]}
    if len(fixed) != len(link["code_literal_relocations"]):
        raise AssertionError("Duplicate code literal relocation")
    pc_refs: dict[tuple[str, int], int] = {}
    external_bl = []
    cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    for p in parts:
        if p["kind"] != "code":
            continue
        source = probe if p["old"] >= 0xC90000 else adopted
        for pos in range(0, p["size"] - 1, 2):
            half = struct.unpack_from("<H", source, p["old"] + pos)[0]
            if half & 0xF800 != 0x4800:
                continue
            literal = ((p["old"] + pos + 4) & ~3) + (half & 255) * 4
            if not p["old"] <= literal <= p["old"] + p["size"] - 4:
                continue
            old = word(source, literal)
            expected = mapped(old)
            if expected is None:
                continue
            relative = literal - p["old"]
            if word(rom, p["new"] + relative) != expected:
                raise AssertionError(f"PC-relative literal wrong: {p['name']} +{relative:x}")
            pc_refs[(p["name"], relative)] = pc_refs.get((p["name"], relative), 0) + 1
        for ins in cs.disasm(source[p["old"]:p["old"] + p["size"]],
                             ROM_BASE + p["old"]):
            if ins.mnemonic != "bl":
                continue
            target = int(ins.op_str.replace("#", ""), 0)
            if not ROM_BASE + p["old"] <= target < ROM_BASE + p["old"] + p["size"]:
                external_bl.append((p["name"], hex(ins.address), hex(target)))
    if set(pc_refs) != set(fixed) or external_bl:
        raise AssertionError(f"Code relocation gap: refs={set(pc_refs)-set(fixed)}, "
                             f"unreferenced={set(fixed)-set(pc_refs)}, BL={external_bl}")
    for (name, relative), entry in fixed.items():
        p = by_name[name]
        source = probe if p["old"] >= 0xC90000 else adopted
        if (word(source, p["old"] + relative) != entry["old"]
                or word(rom, p["new"] + relative) != entry["new"]
                or mapped(entry["old"]) != entry["new"]):
            raise AssertionError(f"Code relocation ledger differs: {name} +{relative:x}")

    hooks = []
    for row in link["hook_veneer_relocations"]:
        at = row["at"]
        if word(rom, at) != row["relocated"] or mapped(row["value"]) != row["relocated"]:
            raise AssertionError(f"Hook target differs at {at:x}")
        if at not in DIRECT_HOOKS and rom[at - 4:at] != bytes.fromhex("004b1847"):
            raise AssertionError(f"Non-veneer hook at {at:x}")
        hooks.append({"storage": hex(at), "old": hex(row["value"]),
                      "target": hex(row["relocated"]),
                      "kind": "named_direct" if at in DIRECT_HOOKS else "thumb_ldr_bx"})

    callsites = []
    for at, target, name in ((0x150C, 0x080CAA18, "odd_full_draw"),
                             (0x1520, 0x080CAA10, "even_full_draw"),
                             (0x1C3B4, 0x0837D980, "select_job"),
                             (0x98980, 0x0837E1B0, "event_allocation")):
        instruction = next(cs.disasm(rom[at:at + 4], ROM_BASE + at, count=1), None)
        if (instruction is None or instruction.mnemonic != "bl"
                or int(instruction.op_str.replace("#", ""), 0) != target):
            raise AssertionError(f"Native BL callsite changed: {name}")
        callsites.append({"name": name, "at": hex(at), "target": hex(target)})
    menu_target = ROM_BASE + link["owned_menus"]["start"] + 1
    if (rom[0x4D98:0x4DA4] != bytes.fromhex("10b4024ca44610bc604700bf")
            or word(rom, 0x4DA4) != menu_target):
        raise AssertionError("Native menu entry/adapter target differs")
    callsites.append({"name": "native_menu_entry", "at": hex(0x4D98),
                      "target": hex(menu_target)})

    # Census every byte phase, then separate source-inherited shapes from new
    # encoded bytes. These are candidates, not automatically live references.
    old_shapes = []
    for at in range(len(rom) - 3):
        value = word(rom, at)
        if not 0x08C00000 <= value < 0x08CB0000 or mapped(value) is None:
            continue
        old_shapes.append((at, value))
    shaped = []
    for at, value in old_shapes:
        owner = next((w["name"] for w in reversed(link["writes"])
                      if w["start"] <= at and at + 4 <= w["end"]), None)
        ldr_sites = []
        if at % 4 == 0:
            for ins in range(max(0, at - 1024), at, 2):
                half = struct.unpack_from("<H", rom, ins)[0]
                if (half & 0xF800 == 0x4800
                        and ((ins + 4) & ~3) + (half & 255) * 4 == at):
                    ldr_sites.append(hex(ins))
        changed = rom[at:at + 4] != jp[at:at + 4]
        if changed and (owner is None or not owner.startswith(ENCODED_OWNERS)):
            raise AssertionError(f"New old-segment shape lacks encoded owner at {at:x}")
        if ldr_sites:
            raise AssertionError(f"Remaining old-segment word has PC LDR at {at:x}")
        shaped.append({"at": hex(at), "value": hex(value), "alignment": at % 4,
                       "changed_from_jp": changed, "owner": owner,
                       "pc_ldr_sites": ldr_sites})

    sys.path.insert(0, str(args.tool_root))
    from strict_relative_assets import read_resource
    relative = []
    for r in link["asset_details"]["relative_assets"]:
        table, index = r["table"], r["index"]
        at = table + 4 + 4 * index
        if word(rom, at) != word(jp, at) or table + word(rom, at) != r["start"]:
            raise AssertionError(f"Restored relative table differs: {table:x}/{index}")
        native, _ = read_resource(rom, r["start"])
        if sha(native) != r["native_sha256"] or len(native) != r["native_bytes"]:
            raise AssertionError(f"Restored resource differs: {table:x}/{index}")
        relative.append({"table": hex(table), "index": index, "target": hex(r["start"])})
    map_rows = []
    table = 0x380F08
    for r in link["asset_details"]["map_assets"]["resources"]:
        at = table + 4 + 4 * r["index"]
        target = table + struct.unpack_from("<i", rom, at)[0]
        native, _ = read_resource(rom, target)
        if (target != r["start"] or sha(native) != r["native_sha256"]
                or len(native) != r["native_bytes"]):
            raise AssertionError(f"Signed map relative entry differs: {r['index']}")
        map_rows.append({"index": r["index"], "target": hex(target),
                         "stored_u32": hex(word(rom, at))})
    for at in (0x376920, 0x37693C):
        if word(rom, at) != word(jp, at):
            raise AssertionError(f"Title-relative source entry differs: {at:x}")
    for r in link["asset_details"]["map_assets"]["layouts"]:
        old_row = 0x2C23B8 + 8 * r["row"]
        if (word(rom, old_row) != ROM_BASE + r["frame"]
                or word(rom, r["frame"] + 4) != ROM_BASE + r["layout"]):
            raise AssertionError(f"Map label relative chain differs: {r['row']}")

    return {"status": "BOUNDED_REFERENCE_CONTRACTS_PASS__CONSUMER_CLOSURE_OPEN",
            "rom_sha256": ROM_SHA, "segment_count": len(parts),
            "code_literal_relocations": len(fixed),
            "pc_relative_literal_sites": sum(pc_refs.values()),
            "external_bl_from_relocated_code": external_bl,
            "hook_relocations": hooks,
            "callsite_contracts": callsites,
            "old_segment_pointer_shapes": shaped,
            "restored_relative_resources": relative,
            "signed_map_relative_resources": map_rows,
            "map_label_chains": len(link["asset_details"]["map_assets"]["layouts"]),
            "qualification": "Exact source and linked bytes only; unresolved game consumers, encoded shapes, ROM mirrors, and dynamic computed references remain open."}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ("japanese", "adopted", "probe", "rom", "link", "tool_root", "out"):
        ap.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError("Fresh audit directory required")
    report = run(args)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "REFERENCE_CONTRACTS.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "pc_relative_literal_sites": report["pc_relative_literal_sites"],
                      "old_segment_pointer_shapes": len(report["old_segment_pointer_shapes"]),
                      "relative_resources": len(report["restored_relative_resources"]),
                      "map_resources": len(report["signed_map_relative_resources"])}))


if __name__ == "__main__":
    main()

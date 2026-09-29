"""Independently verify the private local tone candidate against v1.0 and AN9J."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from bps import apply_bps
from extract_dialogue_book_data import source_text
from narikiri2_text_spec import decode_game_text

EXPECTED_BASE = "7505ef506e4fc11e1e0f36672956627e7522d2441cedfb06a5f359e7f5bd2b50"
EXPECTED_JP = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
EXPECTED_CHANGES = {"D04485:00349634", "D04489:0034965C", "D04499:00349714"}
STEM = "Xagros_Narikiri2_KOR_v1.0_tone-pass01"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(base_path: Path, jp_path: Path, old_book_path: Path, a: Path, b: Path) -> dict:
    base, jp = base_path.read_bytes(), jp_path.read_bytes()
    if digest(base) != EXPECTED_BASE or digest(jp) != EXPECTED_JP:
        raise ValueError("Wrong baseline ROMs")
    rom = (a / (STEM + ".gba")).read_bytes()
    bps = (a / (STEM + "_FROM_JP.bps")).read_bytes()
    if rom != (b / (STEM + ".gba")).read_bytes() or bps != (b / (STEM + "_FROM_JP.bps")).read_bytes():
        raise ValueError("A/B build differs")
    if apply_bps(jp, bps) != rom:
        raise ValueError("JP cumulative patch does not reproduce candidate")
    manifest = json.loads((a / "BUILD_MANIFEST.json").read_text("utf-8"))
    if manifest["base_sha256"] != digest(base) or manifest["target_sha256"] != digest(rom):
        raise ValueError("Build manifest ROM identity mismatch")
    writes = manifest["writes"]
    if {row["binding"] for row in writes} != EXPECTED_CHANGES or len(writes) != 3:
        raise ValueError("Change scope mismatch")
    allowed = {int(row["storage"], 16) + delta for row in writes for delta in range(4)}
    modified = {offset for offset, (before, after) in enumerate(zip(base, rom)) if before != after}
    if not modified <= allowed or len(rom) <= len(base):
        raise ValueError("Unexpected existing ROM byte changed")
    for row in writes:
        storage = int(row["storage"], 16)
        target = struct.unpack_from("<I", rom, storage)[0] - 0x08000000
        if target != int(row["offset"], 16) or target < len(base) or target >= len(rom):
            raise ValueError("Pointer target invalid")
        _, final_raw = source_text(rom, storage)
        if digest(final_raw) != row["payload_sha256"] or decode_game_text(rom, final_raw).replace("\u3000", " ") != row["after"]:
            raise ValueError("Extracted candidate text differs from decision")
        _, prior_raw = source_text(base, storage)
        if prior_raw.count(b"\n") != final_raw.count(b"\n") or prior_raw.count(b"\x12") != final_raw.count(b"\x12"):
            raise ValueError("Control bytes changed")
        if not final_raw or rom[target + len(final_raw)] != 0:
            raise ValueError("Missing final text terminator")
    old = json.loads(old_book_path.read_text("utf-8"))
    new = json.loads((a / "final-dialogue-book.json").read_text("utf-8"))
    if len(old["full"]) != 8945 or len(new["full"]) != 8945 or len(old["compact"]) != 1227 or old["compact"] != new["compact"]:
        raise ValueError("Corpus denominator or compact records changed")
    changed = set()
    for before, after in zip(old["full"], new["full"]):
        if before[0] != after[0]:
            raise ValueError("Corpus order/binding changed")
        storage = int(after[10], 16)
        _, raw = source_text(rom, storage)
        if decode_game_text(rom, raw) != after[5]:
            raise ValueError(f"Workbook source differs from ROM: {after[0]}")
        if before[5] != after[5]:
            changed.add(after[0])
    if changed != EXPECTED_CHANGES:
        raise ValueError(f"Unexpected translated binding changed: {changed}")
    mapping = json.loads((a / "scene_map.json").read_text("utf-8"))
    identity = mapping["source_identity"]
    if (identity["base_rom_sha256"] != digest(base) or identity["candidate_rom_sha256"] != digest(rom)
            or identity["base_corpus_sha256"] != digest(old_book_path.read_bytes())
            or identity["final_corpus_sha256"] != digest((a / "final-dialogue-book.json").read_bytes())):
        raise ValueError("Scene metadata source identity mismatch")
    if mapping["scene_count"] != 2 or len(mapping["records"]) != 34:
        raise ValueError("Scene coverage mismatch")
    for binding in EXPECTED_CHANGES:
        if mapping["records"][binding]["language_review_status"] != "CORRECT_REVIEWED":
            raise ValueError("Corrected binding absent from scene review")
    for binding in ("D02517:00349614", "D04494:003496D4", "D04495:003496E4", "D04508:00349B40"):
        if binding in changed or binding not in mapping["records"]:
            raise ValueError("Shared greeting or addressee-change preservation failed")
    return {
        "result": "PASS", "baseline_sha256": digest(base), "candidate_sha256": digest(rom),
        "japanese_sha256": digest(jp), "bps_sha256": digest(bps),
        "changed_existing_byte_positions": len(modified), "changed_translated_bindings": len(changed),
        "preserved_translated_bindings": len(new["full"]) - len(changed),
        "compact_fields_preserved": len(new["compact"]), "reviewed_static_scene_blocks": mapping["scene_count"],
        "reviewed_static_turns": len(mapping["records"]),
        "runtime_scene_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("base", "japanese", "baseline-book", "build-a", "build-b", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.base, args.japanese, args.baseline_book, args.build_a, args.build_b)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

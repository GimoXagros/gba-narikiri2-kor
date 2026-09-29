"""Independent byte/corpus/BPS audit of the local in-place retest candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from bps import apply_bps
from extract_dialogue_book_data import source_text
from narikiri2_text_spec import decode_game_text

BASE_SHA = "7505ef506e4fc11e1e0f36672956627e7522d2441cedfb06a5f359e7f5bd2b50"
JP_SHA = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
STEM = "Xagros_Narikiri2_KOR_v1.0_tone-pass01-inplace-retest"
EXPECTED = {
    "D04485:00349634": (0x83734E, 36, "404c89738bf181638cde8b62889f81408fe9897e8e9381408cde90aa88ed814094488144"),
    "D04489:0034965C": (0x837296, 28, "89738c43814391ed91ed94c581408ef08acf8140889f8144"),
    "D04499:00349714": (0x83712E, 14, "8a6f81438cfc8c6090aa914e8149"),
}

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def verify(base_path: Path, jp_path: Path, baseline_book: Path,
           prior_book: Path, a: Path, b: Path) -> dict:
    base, jp = base_path.read_bytes(), jp_path.read_bytes()
    if sha(base) != BASE_SHA or sha(jp) != JP_SHA:
        raise ValueError("Wrong source ROM identity")
    rom = (a / (STEM + ".gba")).read_bytes()
    bps = (a / (STEM + "_FROM_JP.bps")).read_bytes()
    if rom != (b / (STEM + ".gba")).read_bytes() or bps != (b / (STEM + "_FROM_JP.bps")).read_bytes():
        raise ValueError("Independent A/B builds differ")
    if len(rom) != len(base) or apply_bps(jp, bps) != rom:
        raise ValueError("ROM length or Japanese BPS round trip differs")
    manifest = json.loads((a / "BUILD_MANIFEST.json").read_text("utf-8"))
    if (manifest["status"] != "LOCAL_RETEST_CANDIDATE_VBA_UNVERIFIED"
            or manifest["base_sha256"] != sha(base) or manifest["target_sha256"] != sha(rom)
            or manifest["japanese_sha256"] != sha(jp) or manifest["bps_sha256"] != sha(bps)):
        raise ValueError("Manifest identity/status mismatch")
    if {w["binding"] for w in manifest["writes"]} != set(EXPECTED) or len(manifest["writes"]) != 3:
        raise ValueError("Changed binding scope mismatch")
    expected_rom = bytearray(base)
    slot_report = []
    for binding, (offset, original_bytes, raw_hex) in EXPECTED.items():
        storage = int(binding.split(":")[1], 16)
        raw = bytes.fromhex(raw_hex)
        slot = raw + b"\0" + bytes(original_bytes-len(raw))
        if len(slot) != original_bytes + 1:
            raise ValueError("Invalid expected original slot capacity")
        if struct.unpack_from("<I", rom, storage)[0] != 0x08000000+offset:
            raise ValueError("Event pointer changed or left original slot")
        original_offset, original_raw = source_text(base, storage)
        if original_offset != offset or len(original_raw) != original_bytes:
            raise ValueError("Baseline slot differs from independent expectation")
        expected_rom[offset:offset+len(slot)] = slot
        new_offset, new_raw = source_text(rom, storage)
        if new_offset != offset or new_raw != raw or rom[offset:offset+len(slot)] != slot:
            raise ValueError("In-place text bytes or zero padding mismatch")
        slot_report.append({"binding":binding,"offset":f"{offset:08X}","old_bytes":original_bytes,
                            "new_bytes":len(raw),"padding_bytes":original_bytes-len(raw),
                            "text":decode_game_text(rom,new_raw)})
    if rom != bytes(expected_rom):
        raise ValueError("ROM bytes changed outside three exact text slots")
    old = json.loads(baseline_book.read_text("utf-8"))
    prior = json.loads(prior_book.read_text("utf-8"))
    new_bytes = (a / "final-dialogue-book.json").read_bytes()
    new = json.loads(new_bytes)
    if any(len(book["full"]) != 8945 or len(book["compact"]) != 1227 for book in (old,prior,new)):
        raise ValueError("Corpus denominator mismatch")
    if old["compact"] != new["compact"] or prior["compact"] != new["compact"]:
        raise ValueError("Compact corpus changed")
    changed = set()
    for baseline_row, prior_row, new_row in zip(old["full"],prior["full"],new["full"]):
        if baseline_row[0] != prior_row[0] or baseline_row[0] != new_row[0]:
            raise ValueError("Corpus binding order changed")
        if prior_row[5:7] != new_row[5:7]:
            raise ValueError("Prior candidate Korean text changed")
        storage = int(new_row[10],16)
        _, raw = source_text(rom,storage)
        if decode_game_text(rom,raw) != new_row[5]:
            raise ValueError(f"Final corpus does not extract from ROM: {new_row[0]}")
        if baseline_row[5] != new_row[5]:
            changed.add(new_row[0])
    if changed != set(EXPECTED):
        raise ValueError(f"Unexpected translated binding change: {changed}")
    mapping = json.loads((a/"scene_map.json").read_text("utf-8"))
    ident = mapping["source_identity"]
    if (ident["base_rom_sha256"] != sha(base) or ident["candidate_rom_sha256"] != sha(rom)
            or ident["base_corpus_sha256"] != sha(baseline_book.read_bytes())
            or ident["final_corpus_sha256"] != sha(new_bytes)
            or len(mapping["records"]) != 34 or mapping["scene_count"] != 2):
        raise ValueError("Scene mapping identity/coverage mismatch")
    return {"result":"PASS","status":manifest["status"],"rom_sha256":sha(rom),
            "rom_bytes":len(rom),"japanese_bps_sha256":sha(bps),
            "changed_byte_positions":sum(x!=y for x,y in zip(base,rom)),
            "changed_full_bindings":len(changed),"full_bindings":len(new["full"]),
            "compact_bindings":len(new["compact"]),"prior_candidate_text_equal":True,
            "slots":slot_report,"vba_user_retest":"NOT_RUN"}

def main():
    p=argparse.ArgumentParser()
    for name in ("base","japanese","baseline-book","prior-candidate-book","build-a","build-b","report"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    report=verify(a.base,a.japanese,a.baseline_book,a.prior_candidate_book,a.build_a,a.build_b)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__":main()

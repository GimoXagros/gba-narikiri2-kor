#!/usr/bin/env python3
"""Prepare a private, source-bound dialogue-book dataset from the AN9J ROM pair."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
import unicodedata
from collections import defaultdict
from pathlib import Path

from narikiri2_text_spec import decode_game_text
from transcribe_compact_font import READINGS

ROOT = Path(__file__).resolve().parents[1]
JP_SHA = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
KR_SHA = "8cf942048d4d03e37775bf5234733a5c049f8210e285173e7876a47db857e0ec"
LATEST_KR_SHA = "64faac67ef9800758cc632af8316232e0d73489178cebac8172d1f2adfd711af"
TOKENS = re.compile(r"@[A-Za-z]|%[0-9]*[A-Za-z]")
COMPACT_FORMAT = re.compile(rb"%[0-9]*[dslkh]")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_text(rom: bytes, storage: int) -> tuple[int, bytes]:
    address = struct.unpack_from("<I", rom, storage)[0]
    offset = address - 0x08000000
    if not 0 <= offset < len(rom):
        raise ValueError(f"Pointer at {storage:08X} leaves ROM")
    end = rom.find(b"\0", offset, min(offset + 8192, len(rom)))
    if end < 0:
        raise ValueError(f"Unterminated text at {offset:08X}")
    return offset, rom[offset:end]


def compact_korean(raw: bytes, glyphs: list[str]) -> str:
    output = []
    i = 0
    while i < len(raw):
        value = raw[i]
        if value == 0x7F:
            if i + 2 >= len(raw):
                raise ValueError("Truncated private-glyph token")
            index = (raw[i + 1] - 1) * 31 + raw[i + 2] - 1
            if not 0 <= index < len(glyphs):
                raise ValueError(f"Unknown private-glyph token {index}")
            output.append(glyphs[index])
            i += 3
        elif value == 10:
            output.append("\n")
            i += 1
        elif value == 37 and (match := COMPACT_FORMAT.match(raw, i)):
            output.append(match.group().decode("ascii"))
            i = match.end()
        elif 32 <= value <= 126 and value - 16 in READINGS:
            output.append(READINGS[value - 16])
            i += 1
        else:
            raise ValueError(f"Unsupported compact byte {value:02X}")
    return unicodedata.normalize("NFC", "".join(output))


def readable(text: str) -> str:
    text = text.replace("\u3000", " ")
    return TOKENS.sub(lambda match: f"⟦{match.group()}⟧", text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--japanese", type=Path, required=True)
    parser.add_argument("--korean", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    jp = args.japanese.read_bytes()
    kr = args.korean.read_bytes()
    jp_sha, kr_sha = sha(jp), sha(kr)
    if jp_sha != JP_SHA or kr_sha not in (KR_SHA, LATEST_KR_SHA):
        raise ValueError("Unrecognized source ROM identity")
    with (ROOT / "analysis/v0.9c/pointer_audit.csv").open(encoding="utf-8-sig", newline="") as stream:
        catalog = list(csv.DictReader(stream))
    groups = defaultdict(list)
    short = []
    for row in catalog:
        if row["kind"] == "full_text":
            groups[row["id"]].append(row)
        elif row["kind"] == "compact":
            short.append(row)
    reviewed = {row["id"] for row in json.loads((ROOT / "translation/v09b_japanese_review.json").read_text(encoding="utf-8"))}
    beta3 = {row["id"] for row in json.loads((ROOT / "translation/v09b_beta3_decisions.json").read_text(encoding="utf-8"))}
    glyphs = json.loads((ROOT / "config/private_glyph_order.json").read_text(encoding="utf-8"))["glyphs"]
    full_rows = []
    token_differences = []
    relocated_bindings = []
    for identity, uses in groups.items():
        for row in uses:
            storage = int(row["storage"], 16)
            jp_offset, jp_raw = source_text(jp, storage)
            kr_offset, kr_raw = source_text(kr, storage)
            if int(row["target"], 16) != kr_offset + 0x08000000:
                if kr_sha == KR_SHA:
                    raise ValueError(f"Catalog/ROM pointer mismatch {identity}:{storage:08X}")
                relocated_bindings.append(f"{identity}:{storage:08X}")
            original = jp_raw.decode("cp932")
            translated = decode_game_text(kr, kr_raw)
            token_status = "일치" if TOKENS.findall(original) == TOKENS.findall(translated) else "차이·확인 필요"
            if token_status != "일치":
                token_differences.append(f"{identity}:{storage:08X}")
            status = "일본어 원문 대조 교정" if identity in reviewed or identity in beta3 else "기존 번역·이번 문학 검수 미실시"
            full_rows.append([
                f"{identity}:{storage:08X}", identity, "본문 문자열·화면 용도 미분류", None,
                original, translated, readable(translated), status, token_status,
                len(uses), f"{storage:08X}", f"{jp_offset:08X}", f"{kr_offset:08X}",
            ])
    compact_rows = []
    for row in short:
        storage = int(row["storage"], 16)
        jp_offset, jp_raw = source_text(jp, storage)
        kr_offset, kr_raw = source_text(kr, storage)
        if int(row["target"], 16) != kr_offset + 0x08000000:
            if kr_sha == KR_SHA:
                raise ValueError(f"Compact catalog/ROM pointer mismatch {row['id']}")
            relocated_bindings.append(f"{row['id']}:{storage:08X}")
        source = jp_raw.decode("cp932")
        translated = compact_korean(kr_raw, glyphs)
        compact_rows.append([
            row["id"], row["id"].rsplit("_", 1)[0],
            source.replace("\x12", "⟦모드전환⟧"),
            unicodedata.normalize("NFKC", source.replace("\x12", "").replace("%h", "")),
            translated, f"{storage:08X}", f"{jp_offset:08X}", f"{kr_offset:08X}",
        ])
    terms = []
    glossary = json.loads((ROOT / "translation/v09a_character_terms.json").read_text(encoding="utf-8"))
    for row in glossary["characters"]:
        terms.append(["등장인물", row["japanese"], row["short"], row["full"], "v09a_character_terms.json"])
    with (ROOT / "translation/reference_costume_names.tsv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            terms.append(["코스튬", row["japanese_compact"], row["reference_name"],
                          row["rom_job_id"], "reference_costume_names.tsv"])
    if len(full_rows) != 8945 or len(compact_rows) != 1227:
        raise ValueError("Text inventory denominator changed")
    result = {
        "meta": {
            "japanese_sha256": jp_sha, "korean_sha256": kr_sha,
            "pointer_catalog_sha256": sha((ROOT / "analysis/v0.9c/pointer_audit.csv").read_bytes()),
            "reference_workbook": "나리키리3_일본어_한국어_대사집_승패조건갱신.xlsx",
            "unique_full_text": len(groups), "full_text_bindings": sum(len(rows) for rows in groups.values()),
            "compact_fields": len(compact_rows), "reviewed_corrections": len(reviewed),
            "beta3_decisions": len(beta3), "token_differences": token_differences,
            "catalog_pointer_relocations": relocated_bindings,
            "scope": "Physical pointer inventory; not game-play order or speaker attribution",
        },
        "full": full_rows,
        "compact": compact_rows,
        "terms": terms,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"rows": len(full_rows), "compact": len(compact_rows), "terms": len(terms),
                      "token_differences": token_differences,
                      "catalog_pointer_relocations": len(relocated_bindings)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Advisory whole-corpus ending scan. It never decides speaker or edits prose."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

POLITE = re.compile(r"(?:요|죠|세요|습니다|습니까)[．！？]")
PLAIN = re.compile(r"(?:야|해|하지|거야|네|줘|봐)[．！？]")


def scan(book: dict, scene_map: dict) -> dict:
    mapped = scene_map["records"]
    candidates = []
    for row in book["full"]:
        text = row[5].replace("\u3000", " ")
        if POLITE.search(text) and PLAIN.search(text):
            candidates.append({"binding_id": row[0], "scene_id": mapped[row[0]]["scene_id"] if row[0] in mapped else "UNKNOWN",
                               "review_status": mapped[row[0]]["language_review_status"] if row[0] in mapped else "NEEDS_SCENE_CONTEXT"})
    return {
        "scan_type": "ADVISORY_REGEX_ONLY",
        "limitations": "Ending patterns are incomplete and may match quotation, different addressee, mixed segments, or natural variation. Zero matches would not mean context review complete.",
        "full_text_bindings_scanned": len(book["full"]),
        "unique_full_text_ids": len({row[1] for row in book["full"]}),
        "compact_fields_outside_this_scan": len(book["compact"]),
        "scene_mapped_bindings": len(mapped),
        "candidate_bindings": len(candidates),
        "candidates_needing_scene_context": sum(row["review_status"] == "NEEDS_SCENE_CONTEXT" for row in candidates),
        "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("book", "scene-map", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    book_data = args.book.read_bytes()
    scene_data = args.scene_map.read_bytes()
    book, mapping = json.loads(book_data), json.loads(scene_data)
    if (mapping["source_identity"]["final_corpus_sha256"] != hashlib.sha256(book_data).hexdigest()
            or mapping["source_identity"]["candidate_rom_sha256"] != book["meta"]["korean_sha256"]):
        raise ValueError("Scanner corpus/scene identity mismatch")
    result = scan(book, mapping)
    if args.out.exists():
        raise ValueError("Preserve previous scan output; choose a new path")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "candidates"}))


if __name__ == "__main__":
    main()

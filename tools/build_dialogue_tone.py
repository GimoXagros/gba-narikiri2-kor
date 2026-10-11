"""Build a source-bound local voice-review candidate from the exact v1.0 ROM."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import struct
import unicodedata
from pathlib import Path

from bps import apply_bps, create_bps
from confirmed_text_edits import encode_full, normalized
from extract_dialogue_book_data import readable, source_text
from narikiri2_text_spec import decode_game_text

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "7505ef506e4fc11e1e0f36672956627e7522d2441cedfb06a5f359e7f5bd2b50"
JP_SHA = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
TOKENS = re.compile(r"@[A-Za-z]|%[0-9]*[A-Za-z]")
PUB_IDS = (
    "D04478", "D04479", "D04480", "D04481", "D02517", "D04482",
    "D04483", "D04484", "D04485", "D04486", "D04487", "D04488",
    "D04489", "D04490", "D04491", "D04492", "D04493", "D04494",
    "D04495", "D04496", "D04497", "D04498", "D04499", "D04500",
)
STREET_IDS = ("D04501", "D04502", "D04503", "D04504", "D04505",
              "D04506", "D04507", "D04508", "D04509", "D04510")
EVENT_BLOCKS = (
    ("intro_pub_rose", 0x3495C8, 0x349728, PUB_IDS),
    ("intro_anasui_street", 0x349AC4, 0x349B64, STREET_IDS),
)
ACTORS = {0x02: "MINT_INFERRED", 0x1E: "RUTZ_INFERRED", 0x20: "ROSE_INFERRED",
          0x3A: "JULIO_INFERRED", 0x3B: "CARO_INFERRED"}
APPROVED_BINDINGS = {
    "D04485:00349634": (0x20, (b"@L",)),
    "D04489:0034965C": (0x20, ()),
    "D04499:00349714": (0x3A, ()),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_identity(base: bytes, jp: bytes) -> None:
    if sha(base) != BASE_SHA or sha(jp) != JP_SHA:
        raise ValueError("Unrecognized v1.0/AN9J source ROM identity")


def inventory() -> dict[int, list[str]]:
    groups: dict[int, list[str]] = {}
    with (ROOT / "analysis/v0.9c/pointer_audit.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["kind"] == "full_text":
                groups.setdefault(int(row["storage"], 16), []).append(row["id"])
    return groups


def scene_map(jp: bytes, base: bytes, result: bytes, catalog: dict[int, list[str]],
              base_corpus: bytes, final_corpus: bytes) -> dict:
    """Map two inspected ROM command blocks; actor names remain scene inferences."""
    records = {}
    for scene_id, start, end, expected_ids in EVENT_BLOCKS:
        actual_ids = []
        block_keys = []
        for command in range(start, end, 8):
            opcode, actor = struct.unpack_from("<HH", jp, command)
            if opcode != 0x0E:
                continue
            storage = command + 4
            ids = catalog.get(storage, [])
            if len(ids) != 1 or actor not in ACTORS:
                raise ValueError(f"Unmapped scene command {command:08X}")
            identity = ids[0]
            actual_ids.append(identity)
            binding = f"{identity}:{storage:08X}"
            block_keys.append(binding)
            _, source_raw = source_text(jp, storage)
            _, before_raw = source_text(base, storage)
            records[binding] = {
                "record_id": identity,
                "binding_id": binding,
                "scene_id": scene_id,
                "event_id": f"rom_{start:08X}_{end:08X}",
                "branch_id": "UNKNOWN",
                "use_site_id": f"{scene_id}:{command:08X}",
                "segment_id": binding + ":speaker_segment_1",
                "turn_id": f"{scene_id}:{command:08X}",
                "order_in_path": len(actual_ids),
                "speaker_id": ACTORS[actor],
                "speaker_slot": f"{actor:04X}",
                "speaker_evidence": f"AN9J opcode 000E actor slot at {command:08X}; identity inferred from scene lines and user report",
                "order_evidence": f"8-byte command at AN9J {command:08X}, pointer storage {storage:08X}; static command order",
                "addressee_id": "UNKNOWN",
                "speech_mode": "dialogue",
                "story_stage": "first_village_tour_user_reported",
                "emotion": "UNKNOWN",
                "confidence": "HIGH_STATIC_SEQUENCE_INFERRED_IDENTITY",
                "previous_turn_ids": [],
                "next_turn_ids": [],
                "source_sha256": sha(source_raw.decode("cp932").encode()),
                "before_sha256": sha(normalized(decode_game_text(base, before_raw)).encode()),
                "language_review_status": "KEEP_CONSISTENT_CONTEXT_REVIEWED",
                "execution_status": "NOT_RUN",
            }
        if tuple(actual_ids) != expected_ids:
            raise ValueError(f"Event command sequence changed at {scene_id}: {actual_ids}")
        for i, key in enumerate(block_keys):
            records[key]["previous_turn_ids"] = [records[block_keys[i - 1]]["turn_id"]] if i else []
            records[key]["next_turn_ids"] = [records[block_keys[i + 1]]["turn_id"]] if i + 1 < len(block_keys) else []
    for identity in ("D04485", "D04489", "D04499"):
        entry = next(v for k, v in records.items() if k.startswith(identity + ":"))
        entry["language_review_status"] = "CORRECT_REVIEWED"
        entry["addressee_id"] = "MINT_INFERRED"
        entry["style_profile_version"] = "rose-intro-v1" if identity != "D04499" else "julio-to-mint-intro-v1"
    for identity in ("D04494", "D04495", "D04504", "D04508", "D04509"):
        entry = next(v for k, v in records.items() if k.startswith(identity + ":"))
        entry["language_review_status"] = "KEEP_INTENTIONAL_ADDRESSEE_CHANGE"
    return {
        "source_identity": {"japanese_sha256": JP_SHA, "base_rom_sha256": sha(base),
                            "candidate_rom_sha256": sha(result), "base_corpus_sha256": sha(base_corpus),
                            "final_corpus_sha256": sha(final_corpus),
                            "pointer_catalog_sha256": sha((ROOT / "analysis/v0.9c/pointer_audit.csv").read_bytes())},
        "scope": "Two inspected ROM command blocks. 000E/pointer interpretation is supported by matching all 34 pointer fields to the inventory; consumer function, cross-block path, and name window are not runtime verified.",
        "scene_count": 2,
        "ordered_turns_in_block": len(records),
        "speaker_profiles": {
            "rose-intro-v1": {
                "profile_id": "rose-intro-v1", "speaker_id": "ROSE_INFERRED", "addressee_id": "MINT_INFERRED",
                "relationship": "first_visit_host_to_guest", "story_stage": "first_village_tour_user_reported",
                "status": "PROVISIONAL_STATIC_SCENE", "register": "informal_familiar",
                "pronouns_and_address": "Explicit Korean pronoun absent in reviewed turn; Rose uses informal endings with the visiting guest.",
                "endings": ["~네", "~야", "~해", "~쉬어"],
                "style_traits": "warm, welcoming pub host; conversational explanation",
                "permitted_exceptions": "switches may be valid for different addressee, quotation, or later relationship change; none shown within this guest exchange",
                "evidence_refs": ["D04482:0034961C", "D04483:00349624", "D04487:00349644", "Japanese.gba:00349618-00349658"],
                "confidence": "HIGH_SCENE_INFERRED"
            },
            "julio-to-mint-intro-v1": {
                "profile_id": "julio-to-mint-intro-v1", "speaker_id": "JULIO_INFERRED", "addressee_id": "MINT_INFERRED",
                "relationship": "young_guide_to_new_guest", "story_stage": "first_village_tour_user_reported",
                "status": "PROVISIONAL_STATIC_SCENE", "register": "polite_conversational",
                "pronouns_and_address": "No explicit Korean pronoun required; speaker uses polite endings toward Mint.",
                "endings": ["~이에요", "~어요", "~죠"],
                "style_traits": "energetic and direct; polite to the guest",
                "permitted_exceptions": "informal speech to Caro at D04494 is a different addressee and is preserved",
                "evidence_refs": ["D04478:003495CC", "D04479:003495D4", "D04491:003496AC", "D04494:003496D4", "Japanese.gba:00349710"],
                "confidence": "HIGH_SCENE_INFERRED"
            },
        },
        "records": records,
    }


def _page_rows(value: str) -> list[int]:
    pages = re.split(r"@P|%k", value)
    return [sum(max(1, math.ceil(len(TOKENS.sub("", line)) / 18)) for line in page.split("\n"))
            for page in pages]


def ascii_marker_controls(raw: bytes) -> tuple[bytes, ...]:
    """Read literal markers while skipping two-byte glyphs whose trail may be '@'."""
    markers = []
    pos = 0
    while pos < len(raw):
        value = raw[pos]
        if 0x80 <= value <= 0x9F or value > 0xDF:
            if pos + 1 >= len(raw):
                raise ValueError("Truncated two-byte glyph")
            pos += 2
        elif value in (ord("@"), ord("%")):
            match = re.match(rb"@[A-Za-z]|%[0-9]*[A-Za-z]", raw[pos:])
            if not match:
                raise ValueError("Unrecognized raw text marker")
            markers.append(match.group())
            pos += len(match.group())
        else:
            pos += 1
    return tuple(markers)


def build(base: bytes, jp: bytes, decisions: list[dict]) -> tuple[bytes, dict]:
    require_identity(base, jp)
    if {row["binding"] for row in decisions} != set(APPROVED_BINDINGS) or len(decisions) != len(APPROVED_BINDINGS):
        raise ValueError("This candidate is restricted to three reviewed scene bindings")
    catalog = inventory()
    result = bytearray(base)
    writes = []
    seen = set()
    for change in decisions:
        if change["decision"] != "CORRECT":
            raise ValueError("Only adjudicated CORRECT decisions may enter this build")
        storage = int(change["storage"], 16)
        if storage in seen or catalog.get(storage) != [change["id"]]:
            raise ValueError(f"Duplicate or unrecognized binding {storage:08X}")
        seen.add(storage)
        if change["binding"] != f"{change['id']}:{storage:08X}":
            raise ValueError("Binding identity mismatch")
        expected_actor, expected_controls = APPROVED_BINDINGS[change["binding"]]
        command = storage - 4
        opcode, actor = struct.unpack_from("<HH", jp, command)
        if opcode != 0x0E or change["use_site_ids"] != [f"intro_pub_rose:{command:08X}"]:
            raise ValueError("Event use-site mismatch")
        if actor != expected_actor or f"ACTOR_{actor:02X}" not in change["speaker_id"]:
            raise ValueError("Event actor mismatch")
        if change["scene_id"] != "intro_pub_rose" or change["affected_bindings"] != [change["binding"]]:
            raise ValueError("Scene scope or affected binding changed")
        expected_profile = "rose-intro-v1" if actor == 0x20 else "julio-to-mint-intro-v1"
        if change["profile_version"] != expected_profile or change["addressee_id"] != "MINT_INFERRED_ACTOR_02":
            raise ValueError("Style profile binding changed")
        _, source_raw = source_text(jp, storage)
        _, before_raw = source_text(base, storage)
        source = source_raw.decode("cp932")
        before = normalized(decode_game_text(base, before_raw))
        after = change["after"]
        if sha(source.encode()) != change["source_sha256"] or sha(before.encode()) != change["before_sha256"]:
            raise ValueError(f"Source or before text hash mismatch: {change['binding']}")
        if before == after or TOKENS.findall(before) != TOKENS.findall(after):
            raise ValueError("No-op or control token changed")
        if ascii_marker_controls(before_raw) != expected_controls:
            raise ValueError("Baseline raw controls differ from reviewed three-binding scope")
        numbers = lambda value: re.findall(r"\d+", unicodedata.normalize("NFKC", TOKENS.sub("", value)))
        if numbers(before) != numbers(after):
            raise ValueError("Numeric content changed")
        if len(before.split("\n")) < len(after.split("\n")) or any(
            new > old for old, new in zip(_page_rows(before), _page_rows(after))
        ) or len(_page_rows(before)) != len(_page_rows(after)):
            raise ValueError("Line/page capacity grew")
        payload = encode_full(after)
        if (ascii_marker_controls(payload) != expected_controls
                or payload.count(b"\n") != before_raw.count(b"\n")
                or payload.count(b"\x12") != before_raw.count(b"\x12")):
            raise ValueError("Raw control bytes changed")
        if normalized(decode_game_text(base, payload)) != after:
            raise ValueError("Encoded text does not round-trip")
        target = len(result)
        if target + len(payload) + 1 > 0x2000000:
            raise ValueError("ROM exceeds GBA range")
        pointer = struct.pack("<I", 0x08000000 + target)
        result.extend(payload + b"\0")
        result[storage:storage + 4] = pointer
        writes.append({**change, "offset": f"{target:08X}", "before_pointer": base[storage:storage + 4].hex(),
                       "after_pointer": pointer.hex(), "payload_sha256": sha(payload)})
    allowed = {int(row["storage"], 16) + i for row in writes for i in range(4)}
    if any(left != right and offset not in allowed for offset, (left, right) in enumerate(zip(base, result))):
        raise ValueError("Unexpected modification to existing ROM data")
    for row in writes:
        storage = int(row["storage"], 16)
        _, raw = source_text(result, storage)
        if normalized(decode_game_text(result, raw)) != row["after"]:
            raise ValueError("Final ROM extraction mismatch")
    return bytes(result), {
        "base_sha256": sha(base), "japanese_sha256": sha(jp), "target_sha256": sha(result),
        "changed_bindings": len(writes), "original_data_moved": False,
        "existing_changes_limited_to_reviewed_pointers": True, "writes": writes,
    }


def final_dataset(base: bytes, result: bytes, book_path: Path, writes: list[dict]) -> dict:
    book = json.loads(book_path.read_text("utf-8"))
    if book["meta"]["korean_sha256"] != sha(base):
        raise ValueError("Dialogue book is not bound to the baseline ROM")
    changed = {row["storage"] for row in writes}
    for row in book["full"]:
        storage = int(row[10], 16)
        _, raw = source_text(result, storage)
        text = decode_game_text(result, raw)
        if row[10] not in changed and text != row[5]:
            raise ValueError(f"Unchanged binding differs from baseline book {row[0]}")
        row[5] = text
        row[6] = readable(text)
        row[12] = f"{source_text(result, storage)[0]:08X}"
        if row[10] in changed:
            row[7] = "말투 교정 pass01"
    book["meta"]["korean_sha256"] = sha(result)
    book["meta"]["tone_review_scope"] = "Two separate static event blocks/34 turns; remaining bindings not context reviewed; cross-block path and runtime identity unverified"
    return book


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("base", "japanese", "changes", "dialogue-book", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Output directory must be new")
    base, jp = args.base.read_bytes(), args.japanese.read_bytes()
    require_identity(base, jp)
    decisions = json.loads(args.changes.read_text("utf-8"))
    result, report = build(base, jp, decisions)
    patch = create_bps(jp, result)
    if apply_bps(jp, patch) != result:
        raise ValueError("Japanese-source cumulative BPS round trip failed")
    book = final_dataset(base, result, args.dialogue_book, report["writes"])
    final_corpus = json.dumps(book, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    mapping = scene_map(jp, base, result, inventory(), args.dialogue_book.read_bytes(), final_corpus)
    args.out.mkdir(parents=True)
    stem = "Xagros_Narikiri2_KOR_v1.0_tone-pass01"
    (args.out / (stem + ".gba")).write_bytes(result)
    (args.out / (stem + "_FROM_JP.bps")).write_bytes(patch)
    (args.out / "BUILD_MANIFEST.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    (args.out / "scene_map.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), "utf-8")
    (args.out / "final-dialogue-book.json").write_bytes(final_corpus)
    print(json.dumps({"rom_sha256": sha(result), "rom_bytes": len(result), "bps_sha256": sha(patch),
                      "bps_bytes": len(patch), "changed_bindings": len(report["writes"]),
                      "scene_ordered_turns": mapping["ordered_turns_in_block"]}))


if __name__ == "__main__":
    main()

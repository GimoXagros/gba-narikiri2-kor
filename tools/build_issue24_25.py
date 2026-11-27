"""Build the local issue #24/#25 candidate over the frozen v1.1c release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from bps import apply_bps, create_bps
from build_v11b import JP, INPUTS, checked_read, require
from build_v11c import TARGET as V11C
from issue24_quest import restore_quest_quotes
from issue25_graphics import restore_battle_graphics


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_pointers(japanese, candidate, rows):
    require(len(rows) == 10371, "Incomplete binding population")
    seen = set()
    for row in rows:
        key = row["binding_id"]
        pointer = int(row["pointer_storage"], 16)
        start = int(row["original_start"], 16)
        expected = (0x08000000 + start).to_bytes(4, "little")
        require(key not in seen and int(row["current_start"], 16) == start,
                f"Duplicate binding or moved start at {key}")
        require(japanese[pointer:pointer+4] == expected == candidate[pointer:pointer+4],
                f"Pointer mismatch at {key}")
        seen.add(key)


def apply_manifest(before, after, records):
    """Every changed byte must have one owner, with guards for both images."""
    result = bytearray(before)
    previous_end = 0
    for record in sorted(records, key=lambda row: row["offset"]):
        start, end = record["offset"], record["end"]
        require(previous_end <= start < end <= len(before), "Overlapping or invalid writer")
        require(sha(before[start:end]) == record["before_sha256"], "Writer input mismatch")
        require(sha(after[start:end]) == record["after_sha256"], "Writer output mismatch")
        result[start:end] = after[start:end]
        previous_end = end
    require(result == after, "Unattributed ROM change")


def write_candidate(out, japanese, baseline, image, records, rows, details):
    require(len(image) == len(japanese) == 0x800000, "Invalid ROM size")
    verify_pointers(japanese, image, rows)
    apply_manifest(baseline, image, records)
    patch = create_bps(japanese, image)
    require(apply_bps(japanese, patch) == image, "Fresh JP BPS application mismatch")
    report = dict(status="LOCAL_CANDIDATE", source_sha256=sha(japanese),
                  baseline_sha256=sha(baseline), rom_sha256=sha(image),
                  patch_sha256=sha(patch), bytes=len(image), pointer_rows=len(rows),
                  pointer_and_start_mismatches=0, writes=records, names=details)
    require(not out.exists(), "Use a new output directory")
    with tempfile.TemporaryDirectory(dir=out.parent) as temp:
        stage = Path(temp)/"candidate"
        stage.mkdir()
        for ext, data in (("gba",image),("bps",patch)):
            (stage / ("issue24-25-candidate."+ext)).write_bytes(data)
        (stage/"BUILD_RESULT.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        os.rename(stage, out)
    return report

def integrate(baseline, patches):
    out = bytearray(baseline)
    all_records = []
    for image, records in patches:
        apply_manifest(baseline, image, records)
        for record in records:
            start, end = record["offset"], record["end"]
            out[start:end] = image[start:end]
        all_records.extend(records)
    apply_manifest(baseline, out, all_records)
    return bytes(out), all_records

def name_writes(base, image, bindings, review):
    """Translate the codec's declared starts to disjoint, hash-guarded writes."""
    blobs = {(int(row["start"], 16), row["bytes"]) for row in review["full_stream_updates"]}
    blobs.update((int(row["start"], 16), row["new_stream_bytes"]) for row in bindings)
    start, size = review["link_book_offsets"]["full"]
    blobs.add((start, size))
    records = []
    for start, size in sorted(blobs):
        end = start + size
        if base[start:end] != image[start:end]:
            records.append(dict(owner="costume_name_codec", offset=start, end=end,
                                before_sha256=sha(base[start:end]), after_sha256=sha(image[start:end])))
    return records


def main():
    from issue25_names import build as rename
    from issue_menu_v4t import fix_menu_scan
    from issue_battle_inspect import fix_battle_inspection
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("japanese", "v11c", "master", "link", "components", "corpus", "out"):
        parser.add_argument("--"+name, required=True, type=Path)
    args = parser.parse_args()
    japanese = checked_read(args.japanese, JP)
    base = checked_read(args.v11c, V11C)
    checked_read(args.link, INPUTS["link"])
    checked_read(args.components, INPUTS["components"])
    rows = json.loads(checked_read(args.corpus, INPUTS["corpus"]))["rows"]
    glossary = Path(__file__).resolve().parents[1]/"docs/issue25-names.csv"
    names, bindings, review = rename(base, japanese, args.master, args.link, glossary, args.components)
    name_plan = name_writes(base, names, bindings, review)
    stages = [restore_quest_quotes(japanese, base), fix_menu_scan(base),
              restore_battle_graphics(japanese, base), fix_battle_inspection(base), (names, name_plan)]
    candidate, records = integrate(base, stages)
    result = write_candidate(args.out, japanese, base, candidate, records, rows,
                             dict(bindings=bindings, codec=review))
    print(json.dumps({k:result[k] for k in ("rom_sha256","patch_sha256","bytes","pointer_rows")}))


if __name__ == "__main__":
    main()

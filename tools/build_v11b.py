"""Reproduce the halfspace candidate from immutable, explicit private inputs.

This build is not release approval; packaging must validate the final QA record.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from bps import apply_bps, create_bps
from build_v11a import checked_read, require

JP = 'a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
BASE = '8823db1cb72f1328136ccfd8fff1fbdca0c8489cbc7ccf90f7e4ecdbb1c37776'
INPUTS = {
    'baseline_patch': '75a16466feaae9612c6827d8fac5faf5b9a40eb968a740d9954aae10be5eadce',
    'link': '82b143f8f7328a45a3a9af41d8284d6362dcda5003be6851a93095e0ce2260ee',
    'components': '5d45d6a100b95cff594c66c1308ac983198994de5a0c33f922f99cb81e3b9468',
    'corpus': 'b1ccdd128a6b75917f0b7f010c6a1e2d032c01c7cf9844320a2e5f4aea8e4ad1',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def merge_graphics(runtime, baseline, graphic, writes):
    """Apply only declared baseline-identical graphic owners after full text."""
    require(len(runtime) == len(baseline) == len(graphic) == 0x800000, 'Image size mismatch')
    result = bytearray(runtime)
    previous = 0
    for row in sorted(writes, key=lambda r: r['start']):
        start, end = row['start'], row['start'] + row['bytes']
        require(previous <= start < end <= len(result), 'Graphic writer overlap/bounds')
        require(runtime[start:end] == baseline[start:end], 'Graphic owner conflicts with full renderer')
        require(sha(baseline[start:end]) == row['before_sha256'], 'Graphic preimage mismatch')
        require(sha(graphic[start:end]) == row['after_sha256'], 'Graphic postimage mismatch')
        result[start:end] = graphic[start:end]
        previous = end
    return bytes(result)


def flatten_compact_writes(before, middle, after, first, second):
    """Verify both stages; permit only the two reviewed allocator call revisions."""
    require(len(before) == len(middle) == len(after) == 0x800000, 'Stage size mismatch')
    for old, new, writes in ((before, middle, first), (middle, after, second)):
        cursor = 0
        for row in sorted(writes, key=lambda r: r['start']):
            lo, hi = row['start'], row['end']
            require(cursor <= lo < hi <= len(old), 'Stage writer overlap/bounds')
            require(old[cursor:lo] == new[cursor:lo], 'Undeclared stage change')
            require(sha(old[lo:hi]) == row['before_sha256'], 'Stage preimage mismatch')
            require(sha(new[lo:hi]) == row['after_sha256'], 'Stage postimage mismatch')
            cursor = hi
        require(old[cursor:] == new[cursor:], 'Undeclared stage tail change')
    calls = {0x35D26E: bytes.fromhex('68f56cfd'), 0x35D280: bytes.fromhex('68f563fd')}
    result = [dict(row) for row in first]
    revised = set()
    for row in second:
        lo, hi = row['start'], row['end']
        overlap = [p for p in first if lo < p['end'] and p['start'] < hi]
        if overlap:
            require(len(overlap) == 1 and lo in calls and hi == lo + 4,
                    'Unreviewed cross-stage overlap')
            parent = overlap[0]
            require((parent['start'], parent['end'], parent['owner']) ==
                    (0x35D23C, 0x35D2C4, 'private_batch_allocate'), 'Wrong allocator owner')
            require(middle[lo:hi] == calls[lo], 'Allocator call preimage changed')
            if lo == 0x35D280:
                require(after[lo:hi] == bytes.fromhex('c046c046'), 'ARM7-compatible skipped call required')
            revised.add(lo)
        else:
            result.append(dict(row))
    require(not revised or revised == set(calls), 'Incomplete allocator call revision')
    for row in result:
        lo, hi = row['start'], row['end']
        row['before_sha256'], row['after_sha256'] = sha(before[lo:hi]), sha(after[lo:hi])
    return sorted(result, key=lambda r: r['start'])


def rebuild(japanese, patch, corpus, link, components, expected_target):
    require(sha(japanese) == JP, 'Japanese source mismatch')
    require(sha(patch) == INPUTS['baseline_patch'], 'Baseline patch mismatch')
    base = apply_bps(japanese, patch)
    require(len(base) == 0x800000 and sha(base) == BASE, 'Baseline mismatch')
    # Keep public source/input guards usable without optional assembler packages.
    from build_halfspace_candidate import candidate
    from build_baked_no_c import build as graphic_build
    from halfspace_compact import compact_overlay, normal_overlay, coverage
    from halfspace_retired_owners import check_text_slots
    full, _, full_report, records, plans = candidate(base, japanese, corpus, link, components)
    graphic, _, _, _, _, graphic_report = graphic_build(base)
    integrated = merge_graphics(full, base, graphic, graphic_report['writes'])
    compact, compact_report = compact_overlay(integrated, base, link, corpus, components)
    result, normal_report = normal_overlay(compact, base, link, corpus, components)
    require(len(result) == 0x800000 and sha(result) == expected_target, 'Expected target mismatch')
    require(len(corpus['rows']) == 10371, 'Corpus population mismatch')
    for row in corpus['rows']:
        storage = int(row['pointer_storage'], 16)
        start = int(row['original_start'], 16)
        require(start == int(row['current_start'], 16), 'Original string start changed')
        require(result[storage:storage+4] == base[storage:storage+4]
                == (0x08000000+start).to_bytes(4, 'little'), 'Original pointer changed')
    final_writes = flatten_compact_writes(integrated, compact, result,
        compact_report['writes'], normal_report['writes'])
    retired_spans=check_text_slots(full,result,corpus,final_writes)
    cumulative = create_bps(japanese, result)
    require(apply_bps(japanese, cumulative) == result, 'Cumulative BPS roundtrip mismatch')
    compact_coverage, _ = coverage(base, corpus, link, components, sha(result), normal_report=normal_report)
    report = dict(status='REPRODUCED_CANDIDATE_REQUIRES_FINAL_QA', source_sha256=JP,
                  baseline_sha256=BASE, target_sha256=sha(result), patch_sha256=sha(cumulative),
                  bytes=len(result), pointer_start_bindings=10371, full=full_report,
                  graphics=graphic_report, compact=compact_report, normal=normal_report,
                  runtime='NOT_RUN_BY_BUILDER')
    report['retired_text_suffix_writes']=retired_spans
    report['final_compact_writes']=final_writes
    return result, cumulative, report, compact_coverage, records, plans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('japanese', *INPUTS, 'out'):
        parser.add_argument('--'+name.replace('_', '-'), type=Path, required=True)
    parser.add_argument('--expected-target', required=True)
    args = parser.parse_args()
    require(not args.out.exists(), 'Output directory already exists')
    require(len(args.expected_target) == 64 and all(c in '0123456789abcdef' for c in args.expected_target),
            'Expected target must be a lowercase SHA-256')
    jp = checked_read(args.japanese, JP)
    data = {key: checked_read(getattr(args, key), digest) for key, digest in INPUTS.items()}
    result, patch, report, cov, records, plans = rebuild(jp, data.pop('baseline_patch'),
        **{key: json.loads(value) for key, value in data.items()}, expected_target=args.expected_target)
    with tempfile.TemporaryDirectory(prefix='.v11b-', dir=args.out.parent) as temporary:
        stage = Path(temporary)/'result'
        stage.mkdir()
        (stage/'Xagros_Narikiri2_KOR_v1.1b.gba').write_bytes(result)
        (stage/'Xagros_Narikiri2_KOR_v1.1b.bps').write_bytes(patch)
        for name, content in [('BUILD_RESULT.json', report), ('COMPACT_COVERAGE.json', cov),
                              ('SPACE_PLAN.json', plans), ('SPACE_RECORDS.json', records)]:
            (stage/name).write_text(json.dumps(content, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        require(not args.out.exists(), 'Output appeared during build')
        os.rename(stage, args.out)
    print(json.dumps({key:report[key] for key in ('status','target_sha256','patch_sha256','bytes')}))


if __name__ == '__main__':
    main()

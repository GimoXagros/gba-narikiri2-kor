"""Rebuild v1.1c from immutable Japanese input and the explicit v1.1b inputs."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from bps import apply_bps, create_bps
from build_v11b import INPUTS, JP, checked_read, rebuild as rebuild_v11b, require, sha
from fix_skill_title_margin import apply_title_margin

BASE = '32ed708c0c8c26074829a163000dd5504a5a7a1fbcd4f1319c2eb1f45d438677'
TARGET = 'bf9e425dc172fb36b0f3ab221a14299898768a8bf5e7e7c36feaf7242f86334c'


def rebuild(japanese, baseline_patch, link, components, corpus):
    base, _, prior, coverage, records, plans = rebuild_v11b(
        japanese, baseline_patch, link=link, components=components, corpus=corpus,
        expected_target=BASE)
    result, fix = apply_title_margin(base)
    require(len(result) == 0x800000 and sha(result) == TARGET, 'Final v1.1c identity mismatch')
    require(result[:0x134C6] == base[:0x134C6]
            and result[0x134C8:] == base[0x134C8:], 'Undeclared v1.1c change')
    for row in corpus['rows']:
        storage, start = int(row['pointer_storage'], 16), int(row['original_start'], 16)
        require(result[storage:storage+4] == base[storage:storage+4]
                == (0x08000000 + start).to_bytes(4, 'little'), 'Original pointer changed')
        require(start == int(row['current_start'], 16), 'Original string moved')
    patch = create_bps(japanese, result)
    require(apply_bps(japanese, patch) == result, 'Cumulative BPS roundtrip mismatch')
    report = dict(status='REPRODUCED_CANDIDATE_REQUIRES_FINAL_QA', source_sha256=JP,
        baseline_sha256=BASE, target_sha256=sha(result), patch_sha256=sha(patch),
        bytes=len(result), pointer_start_bindings=len(corpus['rows']), title_fix=fix,
        previous_build=prior, runtime='NOT_RUN_BY_BUILDER', audio_rom_changes=False)
    return result, patch, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('japanese', *INPUTS, 'out'):
        parser.add_argument('--'+name.replace('_', '-'), type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), 'Output directory already exists')
    japanese = checked_read(args.japanese, JP)
    data = {key: checked_read(getattr(args, key), expected) for key, expected in INPUTS.items()}
    image, patch, report = rebuild(japanese, data.pop('baseline_patch'),
        **{key: json.loads(value) for key, value in data.items()})
    with tempfile.TemporaryDirectory(prefix='.v11c-', dir=args.out.parent) as temporary:
        stage = Path(temporary)/'result'; stage.mkdir()
        (stage/'Xagros_Narikiri2_KOR_v1.1c.gba').write_bytes(image)
        (stage/'Xagros_Narikiri2_KOR_v1.1c.bps').write_bytes(patch)
        (stage/'BUILD_RESULT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        require(not args.out.exists(), 'Output appeared during build')
        os.rename(stage, args.out)
    print(json.dumps({key: report[key] for key in ('status','target_sha256','patch_sha256','bytes')}))


if __name__ == '__main__':
    main()

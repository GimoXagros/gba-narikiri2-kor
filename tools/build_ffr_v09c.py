"""Reproduce frozen game bytes with corrected v0.9c PC candidate tooling."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apply_ffr_v09c import NAME, SOURCE, TARGET, PATCH
from build_ffr_v09b import build as frozen_build
from narikiri2_text_spec import JAPANESE_SHA256
from v09c_io import atomic_write_new, exists_or_link

BUG_IDS = [f'ND2-V09C-20260909-{i:03d}' for i in (1, 2, 3)]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def candidate_manifest(target, patch, baseline):
    if len(target) != 13107200 or sha(target) != TARGET or sha(patch) != PATCH:
        raise ValueError('Unowned game change in a tool-only candidate')
    return dict(version='v0.9c', release_type='candidate', release_authorized=False,
                source_profile='AN9J_FFR_BETA3_071102', source_size=9961472, source_sha256=SOURCE,
                target_size=len(target), target_sha256=sha(target), patch_size=len(patch), patch_sha256=sha(patch),
                baseline_v09b_sha256=TARGET, rom_change_policy='IDENTICAL_TO_V09B_TOOL_FIXES_ONLY',
                included_bug_ids=BUG_IDS, rom_changes=[], unexpected_diff=0, unowned_diff=0,
                compact_name_fields=1227, first_stage_absolute_pointer_bindings=baseline['first_stage_pointer_bindings'],
                baseline_review=baseline['japanese_review'],
                publication_status='LOCAL_PC_CANDIDATE_NOT_AUTHORIZED_FOR_RELEASE',
                runtime_status='SEE_ARTIFACT_BOUND_PC_VERIFICATION')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('beta2-reference', 'beta3', 'japanese-reference', 'output-dir'):
        parser.add_argument('--'+arg, type=Path, required=True)
    args = parser.parse_args()
    inputs = (args.beta2_reference, args.beta3, args.japanese_reference)
    if exists_or_link(args.output_dir) or args.output_dir.resolve() in [p.resolve() for p in inputs]:
        raise ValueError('A new output directory separate from all inputs is required')
    before = [p.read_bytes() for p in inputs]
    if sha(before[1]) != SOURCE or sha(before[2]) != JAPANESE_SHA256:
        raise ValueError('Immutable BETA3/Japanese reference identity mismatch')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    # No release-readiness flag or candidate hash is edited by this operation.
    target, patch, baseline, _ = frozen_build(*before, args.output_dir/'font')
    if any(p.read_bytes() != data for p, data in zip(inputs, before)):
        raise ValueError('REFERENCE_MUTATION_BLOCKER')
    report = candidate_manifest(target, patch, baseline)
    report['japanese_reference_sha256_before'] = report['japanese_reference_sha256_after'] = sha(before[2])
    report['beta3_source_sha256_before'] = report['beta3_source_sha256_after'] = sha(before[1])
    for suffix, data in (('.gba', target), ('_FROM_BETA3.bps', patch)):
        atomic_write_new(args.output_dir/(NAME+suffix), data)
    # The manifest is published last; failure before this never marks a set complete.
    atomic_write_new(args.output_dir/'manifest.json', (json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

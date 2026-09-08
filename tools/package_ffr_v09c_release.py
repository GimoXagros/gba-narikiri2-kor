"""Prepare a LOCAL v0.9c PC candidate ZIP; this never authorizes a release."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apply_ffr_v09c import NAME, TARGET, SOURCE
from build_ffr_v09c import candidate_manifest
from v09c_io import atomic_write_new, exists_or_link

TEXT = {
    'apply_ffr_v09c.py': 'apply_ffr_v09c.py',
    'bps.py': 'tools/bps.py',
    'v09c_io.py': 'tools/v09c_io.py',
    'README.md': 'docs/v0.9c/README.md',
    'V09C_PC_TEST_NOTES.md': 'V09C_PC_VALIDATION.md',
    'HARDWARE_RETEST.md': 'docs/v0.9c/HARDWARE_RETEST.md',
    'verification/v0.9c.json': 'verification/v0.9c.json',
    'LICENSE': 'LICENSE', 'RIGHTS.md': 'RIGHTS.md',
    'THIRD_PARTY_NOTICES.md': 'THIRD_PARTY_NOTICES.md',
    'third_party/dalmoori-font/LICENSE': 'third_party/dalmoori-font/LICENSE',
    'third_party/dalmoori-font/SOURCE_MANIFEST.json': 'third_party/dalmoori-font/SOURCE_MANIFEST.json',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def same_typed_value(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return (actual.keys() == expected.keys() and
                all(same_typed_value(actual[k], v) for k, v in expected.items()))
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            same_typed_value(a, b) for a, b in zip(actual, expected))
    return actual == expected


def validate_manifest(manifest, rom, patch, frozen_gate):
    expected = candidate_manifest(rom, patch, {
        'first_stage_pointer_bindings': 2077,
        'japanese_review': frozen_gate['japanese_review'],
    })
    from narikiri2_text_spec import JAPANESE_SHA256
    expected.update(japanese_reference_sha256_before=JAPANESE_SHA256,
                    japanese_reference_sha256_after=JAPANESE_SHA256,
                    beta3_source_sha256_before=SOURCE, beta3_source_sha256_after=SOURCE)
    if set(manifest) != set(expected):
        raise ValueError('Incomplete or unexpected candidate manifest fields')
    for key, value in expected.items():
        if not same_typed_value(manifest[key], value):
            raise ValueError('Candidate manifest mismatch: '+key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if exists_or_link(args.output_dir):
        raise FileExistsError('Choose a new candidate package directory')
    manifest = json.loads((args.build_dir/'manifest.json').read_text(encoding='utf-8'))
    rom = (args.build_dir/(NAME+'.gba')).read_bytes()
    patch_name = NAME+'_FROM_BETA3.bps'
    patch = (args.build_dir/patch_name).read_bytes()
    frozen = json.loads((ROOT/'verification/v0.9b.json').read_text(encoding='utf-8'))
    validate_manifest(manifest, rom, patch, frozen)
    gate = json.loads((ROOT/'verification/v0.9c.json').read_text(encoding='utf-8'))
    if (gate['pc_validation_status'] != 'PC_VALIDATION_PASS' or
            gate['release_authorized'] is not False or gate['release_type'] != 'candidate' or
            gate['target_sha256'] != TARGET or gate['patch_sha256'] != sha(patch) or
            gate['included_bug_ids'] != manifest['included_bug_ids']):
        raise ValueError('Artifact-bound PC candidate gate not satisfied')
    files = {patch_name: patch}
    for name, relative in TEXT.items():
        path = ROOT/relative
        if path.is_symlink():
            raise ValueError('Candidate package input must not be a link')
        raw = path.read_text(encoding='utf-8').replace('\r\n', '\n').encode('utf-8')
        if b'\0' in raw:
            raise ValueError('Binary text input')
        files[name] = raw
    manifest['rom_included'] = False
    manifest['package_files'] = {n: dict(size=len(data), sha256=sha(data)) for n, data in files.items()}
    files['manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    files['SHA256SUMS.txt'] = ''.join(f'{sha(data)}  {name}\n' for name, data in sorted(files.items())).encode('ascii')
    import io
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 9, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    raw_zip = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        if set(archive.namelist()) != set(files) or any(archive.read(n) != data for n, data in files.items()):
            raise ValueError('Candidate ZIP read-back mismatch')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    archive_name = NAME+'_PC_CANDIDATE.zip'
    for name, data in ((archive_name, raw_zip), (patch_name, patch), ('manifest.json', files['manifest.json'])):
        atomic_write_new(args.output_dir/name, data)
    sums = ''.join(f'{sha((args.output_dir/n).read_bytes())}  {n}\n' for n in sorted((archive_name, patch_name, 'manifest.json')))
    atomic_write_new(args.output_dir/'SHA256SUMS.txt', sums.encode('ascii'))
    print(json.dumps(dict(status='LOCAL_PC_CANDIDATE', release_authorized=False,
                          zip_sha256=sha(raw_zip), zip_size=len(raw_zip), rom_included=False), indent=2))


if __name__ == '__main__':
    main()

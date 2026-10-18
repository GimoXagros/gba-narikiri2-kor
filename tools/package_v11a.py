"""Package an already built v1.1a BPS using an explicit public-file allowlist."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import zipfile

from apply_japanese_patch_v11a import (DOCUMENT_NAMES, PAYLOAD_NAMES, PATCH_NAME,
    MANIFEST_NAME, validate_manifest, verify_patch, require_new_output, sha)
from v09c_io import atomic_write_new

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = 'Xagros_Narikiri2_KOR_v1.1a_JP_PACKAGE.zip'
ARCHIVE_NAMES = frozenset((*PAYLOAD_NAMES, MANIFEST_NAME, 'SHA256SUMS.txt'))
PUBLICATION_QUOTE = '수정된 사항을 확인했어. **v1.1**a로 저장소에 업데이트 및 배포해줘'
VERIFICATION_SCHEMA = 'narikiri2-v11a-verification-1'


def validate_verification_policy(verification, manifest):
    """Pin correction acceptance without inventing runtime or hardware gates."""
    validate_manifest(manifest)
    expected = dict(schema=VERIFICATION_SCHEMA, version='v1.1a', release_eligible=True,
        hardware_status='NOT_REPORTED', runtime_status='NOT_REPORTED',
        individual_checks='NOT_REPORTED',
        cpu_fixture=dict(status='PASS_CPU_FIXTURE_NOT_NORMAL_PLAY', scope='CPU_FIXTURE_ONLY'),
        correction_acceptance=dict(kind='USER_ATTESTED', date='2026-10-19',
            exact_user_quote=PUBLICATION_QUOTE, context='QA597_CORRECTION_8823',
            environment=dict(hardware_model='NOT_REPORTED', emulator='NOT_REPORTED',
                             tested_checks='NOT_REPORTED')))
    for name in ('source', 'target', 'patch'):
        expected[name + '_size'] = manifest[name]['size']
        expected[name + '_sha256'] = manifest[name]['sha256']
        expected['correction_acceptance'][name + '_sha256'] = manifest[name]['sha256']
    if verification != expected or verification.get('release_eligible') is not True:
        raise ValueError('Verification must match the exact v1.1a correction acceptance scope')
    if any(type(verification.get(name + '_size')) is not int for name in ('source', 'target', 'patch')):
        raise ValueError('Verification sizes must be integers')


def public_text(name, data):
    text = data.decode('utf-8')
    if '\0' in text or re.search(r'(?i)(?:(?<![a-z0-9])[a-z]:[\\/]|private_validation[\\/]|/users/|/home/)', text):
        raise ValueError('Non-public content/path in ' + name)
    return data.replace(b'\r\n', b'\n')


def package(japanese: bytes, target: bytes, patch: bytes, manifest: dict, documents: Path):
    validate_manifest(manifest)
    if verify_patch(japanese, patch, manifest) != target:
        raise ValueError('Provided final target differs from verified BPS output')
    entries = {PATCH_NAME: patch}
    for name, file in (('apply_japanese_patch.py', 'apply_japanese_patch_v11a.py'),
                       ('bps.py', 'bps.py'), ('v09c_io.py', 'v09c_io.py')):
        entries[name] = (ROOT / 'tools' / file).read_bytes()
    for name in DOCUMENT_NAMES:
        entries[name] = public_text(name, (Path(documents) / name).read_bytes())
    verification = json.loads(entries['VERIFICATION.json'].decode('utf-8'))
    validate_verification_policy(verification, manifest)
    files = {name: {'size': len(data), 'sha256': sha(data)} for name, data in sorted(entries.items())}
    if 'files' in manifest and manifest['files'] != files:
        raise ValueError('Input manifest payload differs from actual public files')
    final_manifest = dict(manifest, files=files)
    validate_manifest(final_manifest)
    entries[MANIFEST_NAME] = (json.dumps(final_manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    entries['SHA256SUMS.txt'] = ''.join(sha(data) + '  ' + name + '\n'
        for name, data in sorted(entries.items())).encode('ascii')
    if set(entries) != ARCHIVE_NAMES:
        raise ValueError('Public ZIP allowlist differs')
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            item = zipfile.ZipInfo(name, (2026, 10, 19, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            archive.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    result = stream.getvalue()
    with zipfile.ZipFile(BytesIO(result)) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(ARCHIVE_NAMES) or set(archive.namelist()) != ARCHIVE_NAMES:
            raise ValueError('ZIP integrity/allowlist mismatch')
        if any(archive.read(name) != data for name, data in entries.items()):
            raise ValueError('ZIP content mismatch')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('japanese', 'target', 'patch', 'manifest', 'documents', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require_new_output(args.output, (args.japanese, args.target, args.patch, args.manifest))
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    result = package(args.japanese.read_bytes(), args.target.read_bytes(), args.patch.read_bytes(), manifest, args.documents)
    atomic_write_new(args.output, result)
    print(json.dumps({'size': len(result), 'sha256': sha(result)}))


if __name__ == '__main__':
    main()

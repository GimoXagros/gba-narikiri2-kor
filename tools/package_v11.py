"""Package an already built v1.1 BPS using an explicit public-file allowlist."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import zipfile

from apply_japanese_patch_v11 import (DOCUMENT_NAMES, PAYLOAD_NAMES, PATCH_NAME,
    MANIFEST_NAME, validate_manifest, verify_patch, require_new_output, sha)
from v09c_io import atomic_write_new

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = 'Xagros_Narikiri2_KOR_v1.1_JP_PACKAGE.zip'
ARCHIVE_NAMES = frozenset((*PAYLOAD_NAMES, MANIFEST_NAME, 'SHA256SUMS.txt'))


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
    for name, file in (('apply_japanese_patch.py', 'apply_japanese_patch_v11.py'),
                       ('bps.py', 'bps.py'), ('v09c_io.py', 'v09c_io.py')):
        entries[name] = (ROOT / 'tools' / file).read_bytes()
    for name in DOCUMENT_NAMES:
        entries[name] = public_text(name, (Path(documents) / name).read_bytes())
    verification = json.loads(entries['VERIFICATION.json'].decode('utf-8'))
    if (not isinstance(verification, dict) or verification.get('version') != 'v1.1'
            or verification.get('source_sha256') != manifest['source']['sha256']
            or verification.get('target_sha256') != manifest['target']['sha256']
            or verification.get('patch_sha256') != manifest['patch']['sha256']):
        raise ValueError('Verification document identities differ')
    # This tool prepares the current review candidate. Official publication after
    # hardware verification requires an explicit review of this package policy.
    if verification.get('release_eligible') is not False or verification.get('hardware_status') != 'NOT_RUN':
        raise ValueError('Candidate verification must disclose release_eligible=false and hardware_status=NOT_RUN')
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
            item = zipfile.ZipInfo(name, (2026, 10, 11, 0, 0, 0))
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

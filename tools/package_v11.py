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
PUBLICATION_QUOTE = '검증 결과 정상적인것을 확인했어. 깃허브 저장소에 v1.1버전으로 업데이트 해줘'


def validate_verification_policy(verification, manifest):
    """Keep candidate policy or require the exact disclosed user attestation."""
    validate_manifest(manifest)
    if (not isinstance(verification, dict) or verification.get('version') != 'v1.1'
            or any(verification.get(name + '_sha256') != manifest[name]['sha256']
                   for name in ('source', 'target', 'patch'))):
        raise ValueError('Verification document identities differ')
    if verification.get('release_eligible') is False and verification.get('hardware_status') == 'NOT_RUN':
        return
    if verification.get('release_eligible') is not True or verification.get('hardware_status') != 'USER_ATTESTED':
        raise ValueError('Candidate verification or explicit USER_ATTESTED publication required')
    if any(verification.get(name + '_size') != manifest[name]['size']
           or type(verification.get(name + '_size')) is not int for name in ('source', 'target', 'patch')):
        raise ValueError('Publication verification sizes differ')
    gates = verification.get('gates')
    if (not isinstance(gates, dict) or set(gates) != {'G' + str(i) for i in range(11)}
            or any(not isinstance(gate, dict) or gate.get('status') != 'PASS' for gate in gates.values())):
        raise ValueError('Publication requires recorded G0-G10 PASS')
    expected = dict(kind='USER_ATTESTED', date='2026-10-11', exact_user_quote=PUBLICATION_QUOTE,
        context='FINAL_VALIDATION_9FD', source_sha256=manifest['source']['sha256'],
        target_sha256=manifest['target']['sha256'], patch_sha256=manifest['patch']['sha256'],
        environment=dict(hardware_model='NOT_REPORTED', emulator='NOT_REPORTED', tested_checks='NOT_REPORTED'))
    if verification.get('scope_decision') != expected:
        raise ValueError('Exact user-attested publication scope differs or is missing')
    # User acceptance resolves the publication scope. It does not supply a
    # hardware model, emulator identity, or individually observed hardware checks.
    if (set(gates['G8']) - {'status', 'scope', 'basis', 'individual_checks'}
            or gates['G8'].get('basis') != 'USER_ATTESTED_SCOPE'
            or gates['G8'].get('individual_checks') != 'NOT_REPORTED'):
        raise ValueError('G8 must distinguish user attestation from individual hardware evidence')


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

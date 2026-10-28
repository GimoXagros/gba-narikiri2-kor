"""Package an already built v1.1b BPS using an explicit public-file allowlist."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import zipfile

from apply_japanese_patch_v11b import (DOCUMENT_NAMES, PAYLOAD_NAMES, PATCH_NAME,
    MANIFEST_NAME, validate_manifest, verify_patch, require_new_output, sha)
from v09c_io import atomic_write_new

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = 'Xagros_Narikiri2_KOR_v1.1b_JP_PACKAGE.zip'
ARCHIVE_NAMES = frozenset((*PAYLOAD_NAMES, MANIFEST_NAME, 'SHA256SUMS.txt'))
PUBLICATION_QUOTE = '남은 반각화 작업과 독립 검증을 계속 진행해줘. 원래 포인터·문자열 위치·8MiB 크기를 유지하고, 최종 검증까지 통과하면 v1.1b로 배포해줘. 작업은 각각 하위 전문가 에이전트를 이용해줘'
VERIFICATION_SCHEMA = 'narikiri2-v11b-verification-1'
EVIDENCE_SCHEMA = 'narikiri2-v11b-evidence-1'
GATE_SCOPES = {
    'reproducible_build': 'EXACT_CANDIDATE_ISOLATED_REBUILD',
    'rom_layout': 'ORIGINAL_POINTERS_STARTS_AND_8MIB',
    'binary_ownership': 'OWNED_WRITES_AND_READBACK',
    'cpu_fixtures': 'CPU_FIXTURES_NOT_NORMAL_PLAY',
    'headless_runtime': 'VIRTUAL_GUEST_EXECUTION_SCOPED_SCENARIOS',
    'save_restore': 'COPIED_SAVE_AND_STATE_RESTORE',
    'performance': 'ORIGINAL_FIXED_GUEST_FRAME_BENCHMARKS',
    'independent_review': 'FINAL_HASH_INDEPENDENT_REVIEW',
    'bps_roundtrip': 'EXACT_JAPANESE_TO_FINAL_TARGET',
    'package_preflight': 'PUBLIC_ALLOWLIST_PRIVACY_AND_PACKAGE_TESTS',
}
PERFORMANCE_LIMITS = {
    'item': (1560, 8, 2), 'monster': (1420, 8, 4), 'costume': (2000, 7, 3),
    'character': (220, 17, 2), 'buy': (1050, 7, 2), 'sell': (1080, 7, 2),
}
LIMITATIONS = ['PHYSICAL_HARDWARE_NOT_RUN', 'NATURAL_BRANCH_COVERAGE_NOT_EXHAUSTIVE',
              'NATIVE_SPACING_EXCEPTIONS_PRESERVED', 'LINK_PLAY_NOT_RUN']


def canonical_record(record):
    return (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def validate_evidence(evidence, manifest):
    validate_manifest(manifest)
    if (type(evidence) is not dict or set(evidence) != {'schema', 'target_sha256', 'gates'}
            or evidence['schema'] != EVIDENCE_SCHEMA
            or evidence['target_sha256'] != manifest['target']['sha256']
            or type(evidence['gates']) is not dict or set(evidence['gates']) != set(GATE_SCOPES)):
        raise ValueError('Evidence schema, target or gate keys differ')
    for key, scope in GATE_SCOPES.items():
        record = evidence['gates'][key]
        fields = {'status', 'scope', 'target_sha256', 'summary', 'checks_count', 'source_report_sha256'}
        if key == 'performance': fields.add('metrics')
        if (type(record) is not dict or set(record) != fields or record['status'] != 'PASS'
                or record['scope'] != scope or record['target_sha256'] != manifest['target']['sha256']
                or type(record['summary']) is not str or not record['summary'].strip()
                or type(record['checks_count']) is not int or record['checks_count'] < 1
                or type(record['source_report_sha256']) is not str
                or not re.fullmatch('[0-9a-f]{64}', record['source_report_sha256'])):
            raise ValueError('Evidence gate mismatch: ' + key)
        public_text(key, canonical_record(record))
        if key == 'performance':
            metrics = record['metrics']
            if type(metrics) is not dict or set(metrics) != set(PERFORMANCE_LIMITS):
                raise ValueError('Performance scenario keys differ')
            for scenario, (samples, p99, display) in PERFORMANCE_LIMITS.items():
                row = metrics[scenario]
                if (type(row) is not dict or set(row) != {'movements', 'p99', 'display_max', 'unresolved'}
                        or any(type(value) is not int for value in row.values())
                        or row['movements'] != samples or not 0 < row['p99'] <= p99
                        or not 0 <= row['display_max'] <= display or row['unresolved'] != 0):
                    raise ValueError('Performance gate failed: ' + scenario)
    return evidence


def verification_record(manifest, evidence):
    """Derive eligibility only after validating all exact-candidate gate records."""
    validate_evidence(evidence, manifest)
    result = dict(schema=VERIFICATION_SCHEMA, version='v1.1b', release_eligible=True,
        hardware_status='NOT_RUN', user_final_artifact_acceptance='NOT_REPORTED',
        authorization=dict(kind='USER_REQUESTED_CONDITIONAL', exact_user_quote=PUBLICATION_QUOTE,
                           condition='ALL_APPLICABLE_FINAL_CANDIDATE_GATES_PASS'),
        limitations=LIMITATIONS.copy(), gates={})
    for name in ('source', 'target', 'patch'):
        result[name + '_size'] = manifest[name]['size']
        result[name + '_sha256'] = manifest[name]['sha256']
    for key, scope in GATE_SCOPES.items():
        result['gates'][key] = dict(status='PASS', scope=scope,
            target_sha256=manifest['target']['sha256'],
            report_sha256=sha(canonical_record(evidence['gates'][key])))
    return result


def validate_verification_policy(verification, manifest, evidence):
    expected = verification_record(manifest, evidence)
    if type(verification) is not dict or verification != expected or verification.get('release_eligible') is not True:
        raise ValueError('Verification must match exact v1.1b conditional authorization and evidence')
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
    for name, file in (('apply_japanese_patch.py', 'apply_japanese_patch_v11b.py'),
                       ('bps.py', 'bps.py'), ('v09c_io.py', 'v09c_io.py')):
        entries[name] = (ROOT / 'tools' / file).read_bytes()
    for name in DOCUMENT_NAMES:
        entries[name] = public_text(name, (Path(documents) / name).read_bytes())
    verification = json.loads(entries['VERIFICATION.json'].decode('utf-8'))
    validate_verification_policy(verification, manifest, json.loads(entries['EVIDENCE.json'].decode('utf-8')))
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
            item = zipfile.ZipInfo(name, (2026, 10, 28, 0, 0, 0))
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

"""Build a deterministic v1.0 Japanese-input patch ZIP from an explicit allowlist."""
import argparse
import json
from io import BytesIO
from pathlib import Path
import zipfile

from apply_japanese_patch_v1 import (
    SOURCE_SHA256, TARGET_SHA256, PATCH_SHA256, SOURCE_SIZE, TARGET_SIZE,
    PATCH_NAME, METADATA, sha,
)
from bps import create_bps, apply_bps
from v09c_io import atomic_write_new

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = 'Xagros_Narikiri2_KOR_v1.0_JP_PACKAGE.zip'


def package(japanese: bytes, target: bytes):
    if len(japanese) != SOURCE_SIZE or sha(japanese) != SOURCE_SHA256:
        raise ValueError('Japanese source identity mismatch')
    if len(target) != TARGET_SIZE or sha(target) != TARGET_SHA256:
        raise ValueError('Final target identity mismatch')
    patch = create_bps(japanese, target, METADATA)
    if sha(patch) != PATCH_SHA256 or apply_bps(japanese, patch) != target:
        raise ValueError('BPS identity or roundtrip mismatch')
    entries = {PATCH_NAME: patch}
    # The version-specific source is named apply_japanese_patch.py inside the ZIP.
    for name, source in (
        ('apply_japanese_patch.py', 'tools/apply_japanese_patch_v1.py'),
        ('bps.py', 'tools/bps.py'),
        ('v09c_io.py', 'tools/v09c_io.py'),
        ('README.txt', 'docs/V1_PACKAGE.md'),
        ('CREDITS.md', 'CREDITS.md'),
        ('RIGHTS.md', 'RIGHTS.md'),
        ('LICENSE', 'LICENSE'),
        ('THIRD_PARTY_NOTICES.md', 'THIRD_PARTY_NOTICES.md'),
        ('VERIFICATION.json', 'verification/v1.0.json'),
        ('DALMOORI_LICENSE', 'third_party/dalmoori-font/LICENSE'),
    ):
        entries[name] = (ROOT / source).read_bytes()
    internal_manifest = {
        'version': 'v1.0', 'source_sha256': SOURCE_SHA256,
        'target_sha256': TARGET_SHA256, 'patch_sha256': PATCH_SHA256,
        'files': {name: {'size': len(data), 'sha256': sha(data)}
                  for name, data in sorted(entries.items())},
    }
    entries['MANIFEST.json'] = (json.dumps(internal_manifest, ensure_ascii=False,
                                          sort_keys=True, indent=2) + '\n').encode('utf-8')
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            entry = zipfile.ZipInfo(name, (2026, 9, 23, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)
    result = stream.getvalue()
    with zipfile.ZipFile(BytesIO(result)) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(entries):
            raise ValueError('ZIP integrity or allowlist mismatch')
        if any(archive.read(name) != data for name, data in entries.items()):
            raise ValueError('ZIP content mismatch')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--japanese', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = package(args.japanese.read_bytes(), args.target.read_bytes())
    atomic_write_new(args.output, data)
    print(json.dumps({'size': len(data), 'sha256': sha(data)}))


if __name__ == '__main__':
    main()

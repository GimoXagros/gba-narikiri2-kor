"""Create the reproducible v0.9d original-Japanese-input package; no ROM or save."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import zipfile

from apply_japanese_patch import (SOURCE_SHA256, TARGET_SHA256, PATCH_SHA256,
                                  SOURCE_SIZE, TARGET_SIZE, PATCH_NAME, METADATA, sha)
from bps import create_bps, apply_bps
from v09c_io import atomic_write_new

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = 'Xagros_Narikiri2_KOR_v0.9d_JP_PACKAGE.zip'


def package(japanese, target):
    gate=json.loads((ROOT/'verification/v0.9d.json').read_text(encoding='utf-8'))
    if not gate.get('release_ready') or (gate.get('source_sha256'),gate.get('target_sha256'),gate.get('patch_sha256')) != (SOURCE_SHA256,TARGET_SHA256,PATCH_SHA256):
        raise ValueError('Artifact-bound v0.9d prerelease verification gate not satisfied')
    if len(japanese) != SOURCE_SIZE or sha(japanese) != SOURCE_SHA256:
        raise ValueError('Japanese source mismatch')
    if len(target) != TARGET_SIZE or sha(target) != TARGET_SHA256:
        raise ValueError('Verified v0.9d target mismatch')
    delta = create_bps(japanese, target, METADATA)
    if sha(delta) != PATCH_SHA256 or apply_bps(japanese, delta) != target:
        raise ValueError('BPS identity or roundtrip mismatch')
    entries = {PATCH_NAME: delta}
    for file in ('apply_japanese_patch.py', 'bps.py', 'v09c_io.py'):
        entries[file] = (ROOT/'tools'/file).read_bytes()
    for name, source in [('README.txt', 'docs/V09D_PACKAGE.md'), ('CREDITS.md', 'CREDITS.md'),
                         ('RIGHTS.md', 'RIGHTS.md'), ('LICENSE', 'LICENSE'),
                         ('THIRD_PARTY_NOTICES.md', 'THIRD_PARTY_NOTICES.md'),
                         ('VERIFICATION.json', 'verification/v0.9d.json'),
                         ('DALMOORI_LICENSE', 'third_party/dalmoori-font/LICENSE')]:
        entries[name] = (ROOT/source).read_bytes()
    manifest = dict(version='v0.9d',prerelease=True,source_sha256=sha(japanese),target_sha256=sha(target),
                    files={n:dict(size=len(b),sha256=sha(b)) for n,b in sorted(entries.items())})
    entries['MANIFEST.json'] = (json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            entry = zipfile.ZipInfo(name, (2026,9,13,0,0,0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)
    result = stream.getvalue()
    with zipfile.ZipFile(BytesIO(result)) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(entries):
            raise ValueError('ZIP verification failed')
        if any(archive.read(n) != b for n,b in entries.items()):
            raise ValueError('ZIP member mismatch')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--japanese',type=Path,required=True)
    p.add_argument('--target',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    data=package(a.japanese.read_bytes(),a.target.read_bytes())
    atomic_write_new(a.output,data)
    print(json.dumps(dict(size=len(data),sha256=sha(data))))


if __name__ == '__main__':
    main()

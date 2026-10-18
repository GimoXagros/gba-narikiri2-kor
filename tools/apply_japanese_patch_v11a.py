"""Apply the manifest-pinned v1.1a patch to the exact AN9J Japanese source."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from bps import apply_bps
from v09c_io import atomic_write_new, exists_or_link

SOURCE_SHA256 = 'a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
TARGET_SHA256 = '8823db1cb72f1328136ccfd8fff1fbdca0c8489cbc7ccf90f7e4ecdbb1c37776'
SOURCE_SIZE = TARGET_SIZE = 8388608
PATCH_SIZE = 378236
PATCH_SHA256 = '75a16466feaae9612c6827d8fac5faf5b9a40eb968a740d9954aae10be5eadce'
PATCH_NAME = 'Xagros_Narikiri2_KOR_v1.1a.bps'
MANIFEST_NAME = 'manifest.json'
SCHEMA = 'narikiri2-v11a-package-1'
DOCUMENT_NAMES = ('README.txt', 'VERIFICATION.json', 'CREDITS.md', 'RIGHTS.md',
                  'LICENSE', 'THIRD_PARTY_NOTICES.md', 'DALMOORI_LICENSE')
PAYLOAD_NAMES = (PATCH_NAME, 'apply_japanese_patch.py', 'bps.py', 'v09c_io.py', *DOCUMENT_NAMES)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_manifest(manifest):
    """Require both the fixed clean-build BPS pin and the matching manifest."""
    if not isinstance(manifest, dict) or set(manifest) not in (
            {'schema', 'version', 'source', 'target', 'patch'},
            {'schema', 'version', 'source', 'target', 'patch', 'files'}):
        raise ValueError('Manifest fields differ')
    if manifest['schema'] != SCHEMA or manifest['version'] != 'v1.1a':
        raise ValueError('Manifest schema/version mismatch')
    for name, size, identity in (('source', SOURCE_SIZE, SOURCE_SHA256),
                                 ('target', TARGET_SIZE, TARGET_SHA256)):
        record = manifest[name]
        if not isinstance(record, dict) or set(record) != {'size', 'sha256'}:
            raise ValueError('Manifest ' + name + ' fields differ')
        if type(record['size']) is not int or record != {'size': size, 'sha256': identity}:
            raise ValueError('Manifest ' + name + ' identity mismatch')
    patch = manifest['patch']
    if not isinstance(patch, dict) or set(patch) != {'name', 'size', 'sha256'}:
        raise ValueError('Manifest patch fields differ')
    if patch['name'] != PATCH_NAME or type(patch['size']) is not int or patch['size'] < 16:
        raise ValueError('Manifest patch name/size mismatch')
    if not isinstance(patch['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', patch['sha256']):
        raise ValueError('Manifest patch SHA-256 required')
    if (patch['size'], patch['sha256']) != (PATCH_SIZE, PATCH_SHA256):
        raise ValueError('Manifest patch identity differs from reviewed clean build')
    if 'files' in manifest:
        files = manifest['files']
        if not isinstance(files, dict) or set(files) != set(PAYLOAD_NAMES):
            raise ValueError('Manifest payload allowlist mismatch')
        for record in files.values():
            if (not isinstance(record, dict) or set(record) != {'size', 'sha256'}
                    or type(record['size']) is not int or record['size'] < 0
                    or not isinstance(record['sha256'], str)
                    or not re.fullmatch('[0-9a-f]{64}', record['sha256'])):
                raise ValueError('Manifest payload identity invalid')
        if files[PATCH_NAME] != {'size': patch['size'], 'sha256': patch['sha256']}:
            raise ValueError('Manifest patch/file identities differ')
    return manifest


def require_new_output(output, inputs=()):
    output = Path(output)
    if exists_or_link(output):
        raise FileExistsError('Output exists; choose a new filename')
    resolved = output.resolve(strict=False)
    if any(resolved == Path(path).resolve(strict=True) for path in inputs):
        raise ValueError('Output must differ from all inputs')


def verify_patch(source, patch, manifest):
    validate_manifest(manifest)
    if len(source) != SOURCE_SIZE or sha(source) != SOURCE_SHA256:
        raise ValueError('Input must be the documented unmodified 8 MiB AN9J Japanese ROM')
    if len(patch) != manifest['patch']['size'] or sha(patch) != manifest['patch']['sha256']:
        raise ValueError('Patch identity mismatch')
    target = apply_bps(source, patch)
    if len(target) != TARGET_SIZE or sha(target) != TARGET_SHA256:
        raise ValueError('Final v1.1a target identity mismatch')
    return target


def apply(source: Path, patch: Path, output: Path, manifest: Path):
    require_new_output(output, (source, patch, manifest))
    identity = json.loads(Path(manifest).read_text(encoding='utf-8'))
    target = verify_patch(Path(source).read_bytes(), Path(patch).read_bytes(), identity)
    atomic_write_new(output, target)
    return sha(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--patch', type=Path, default=Path(__file__).with_name(PATCH_NAME))
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name(MANIFEST_NAME))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print('PASS: ' + apply(args.rom, args.patch, args.output, args.manifest))


if __name__ == '__main__':
    main()

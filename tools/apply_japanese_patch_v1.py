"""Apply the v1.0 patch to the exact unmodified AN9J Japanese ROM."""
import argparse
import hashlib
from pathlib import Path

from bps import apply_bps
from v09c_io import atomic_write_new

SOURCE_SHA256 = 'a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
TARGET_SHA256 = '7505ef506e4fc11e1e0f36672956627e7522d2441cedfb06a5f359e7f5bd2b50'
PATCH_SHA256 = '8d4a102714dccca1228215d97ae38b55eaca7ed9b74552150d3ab6aee2fa16e6'
SOURCE_SIZE = 8388608
TARGET_SIZE = 13270790
PATCH_NAME = 'Xagros_Narikiri2_KOR_v1.0.bps'
METADATA = b'Xagros Korean patch v1.0; original translation contribution: FFR team'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def apply(source: Path, patch: Path, output: Path):
    original = source.read_bytes()
    if len(original) != SOURCE_SIZE or sha(original) != SOURCE_SHA256:
        raise ValueError('Input must be the unmodified 8 MiB AN9J Japanese ROM with the documented SHA-256')
    delta = patch.read_bytes()
    if sha(delta) != PATCH_SHA256:
        raise ValueError('Patch SHA-256 mismatch')
    target = apply_bps(original, delta)
    if len(target) != TARGET_SIZE or sha(target) != TARGET_SHA256:
        raise ValueError('Output identity mismatch')
    atomic_write_new(output, target)
    return sha(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--patch', type=Path, default=Path(__file__).with_name(PATCH_NAME))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print('PASS: ' + apply(args.rom, args.patch, args.output))


if __name__ == '__main__':
    main()

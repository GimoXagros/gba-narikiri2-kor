"""Apply Xagros's Korean graphics test patch to the unmodified AN9J Japanese ROM."""
import argparse
import hashlib
from pathlib import Path

from bps import apply_bps
from v09c_io import atomic_write_new

SOURCE_SHA256 = 'a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
TARGET_SHA256 = 'e9dbed3a744100b02ec1e0a67c153dda850d5c95fcfe32803008397ae6c9a04a'
PATCH_SHA256 = 'e483eb112ba2b0480aa6fd0e7eeb69b14165473bf0741c672b9a06145c8f7c68'
SOURCE_SIZE = 8388608
TARGET_SIZE = 13107200
PATCH_NAME = 'Xagros_Narikiri2_KOR_v0.9d_test.bps'
METADATA = b'Xagros Korean patch v0.9d graphics test; original translation contribution: FFR team'


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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('rom', type=Path)
    p.add_argument('--patch', type=Path, default=Path(__file__).with_name(PATCH_NAME))
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print('PASS: ' + apply(a.rom, a.patch, a.output))


if __name__ == '__main__':
    main()

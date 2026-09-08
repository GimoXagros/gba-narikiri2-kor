"""Apply the local v0.9c PC candidate to exact FFR BETA3(071102)."""
import argparse
import hashlib
from pathlib import Path
import sys

if (Path(__file__).resolve().parent/'tools').is_dir():
    sys.path.insert(0, str(Path(__file__).resolve().parent/'tools'))
from bps import apply_bps
from v09c_io import atomic_write_new, exists_or_link

NAME = 'NARIKIRI2_AN9J_K_DALMOORI_v0.9c'
SOURCE = 'c6d7a401aa2a22362b2d27d0d31632cb2180a86b094788815d949b84c7fc944d'
# This candidate changes PC tooling only. Byte identity to the independently
# reproduced frozen game is a constraint, not a newly blessed build hash.
TARGET = 'd761088a8549cb5bc60a2f03a4b78eea5282dbc17ed5da4ef1de27da4ad8d4d4'
PATCH = '51dbdb8ef24a32ca5efb05ec3196b98ae08a32f3a4d6bb88673d58266837dcf6'


def checked(source, patch):
    sha = lambda data: hashlib.sha256(data).hexdigest()
    if len(source) != 9961472 or sha(source) != SOURCE:
        raise ValueError('Exact original FFR BETA3(071102) required')
    if source[0xAC:0xB0] != b'AN9J' or source[0xBD] != (-sum(source[0xA0:0xBD])-0x19)&255:
        raise ValueError('AN9J header mismatch')
    if sha(patch) != PATCH:
        raise ValueError('Not the verified BETA3 cumulative candidate patch')
    target = apply_bps(source, patch)
    if len(target) != 13107200 or sha(target) != TARGET:
        raise ValueError('Tool-only candidate must preserve frozen v0.9b game bytes')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--patch', type=Path, default=Path(__file__).with_name(NAME+'_FROM_BETA3.bps'))
    parser.add_argument('--output', type=Path, default=Path(NAME+'.gba'))
    args = parser.parse_args()
    if exists_or_link(args.output):
        raise FileExistsError('Output exists; choose a new filename')
    if args.output.resolve() in (args.source.resolve(), args.patch.resolve()):
        raise ValueError('Input and output paths must be separate')
    target = checked(args.source.read_bytes(), args.patch.read_bytes())
    atomic_write_new(args.output, target)
    print('Verified local PC candidate: '+str(args.output.resolve()))
    print('Game bytes unchanged from v0.9b. Hardware retest pending; see included release notes.')
    print('SHA-256: '+TARGET)


if __name__ == '__main__':
    main()

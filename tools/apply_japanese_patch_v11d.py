"""Apply the v1.1d cumulative BPS to the verified Japanese AN9J image."""
import argparse
from hashlib import sha256
from pathlib import Path

from bps import apply_bps
from v09c_io import atomic_write_new


SIZE = 0x800000
SOURCE = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
PATCH = "0ec5c689b01072745b37239bb30e0bc0e3b36c65d8e90d04bb348c807c7f982e"
TARGET = "705d92a147ac1e3bd4830ca976154dd397c67263ad99dcd04a8dd5313d9e0177"
PATCH_NAME = "Xagros_Narikiri2_KOR_v1.1d.bps"


def verified(data, length, digest, label):
    if len(data) != length or sha256(data).hexdigest() != digest:
        raise ValueError(f"{label} size or SHA-256 differs")
    return data


def apply(source, patch, output):
    original = verified(source.read_bytes(), SIZE, SOURCE, "Japanese AN9J source ROM")
    delta = verified(patch.read_bytes(), 381753, PATCH, "v1.1d patch")
    target = verified(apply_bps(original, delta), SIZE, TARGET, "Patched ROM")
    atomic_write_new(output, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--patch", type=Path, default=Path(__file__).with_name(PATCH_NAME))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    apply(args.rom, args.patch, args.output)
    print(f"{TARGET}  {args.output.name}")


if __name__ == "__main__":
    main()

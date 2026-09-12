"""Local v0.9c graphics repair: original Namco credit and formation RL header.

Requires the user's exact Japanese reference ROM; no original graphics bundled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bps import apply_bps, create_bps
from gba_rl import decompress

BASE_SHA = "d761088a8549cb5bc60a2f03a4b78eea5282dbc17ed5da4ef1de27da4ad8d4d4"
JP_SHA = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
SPLASH = (0x37FC34, 0x3800B2)
SELECTOR = 0x3AC1D8


def sha(data):
    return hashlib.sha256(data).hexdigest()


def repair(base: bytes, japanese: bytes):
    if sha(base) != BASE_SHA or sha(japanese) != JP_SHA:
        raise ValueError("Only the exact v0.9c baseline and AN9J Japanese reference are accepted")
    # Relative resource tables and next resource boundaries must remain intact.
    for table, index, offset in [(0x3768F8, 18, SPLASH[0]), (0x3A7ADC, 48, SELECTOR)]:
        entry = table + 4 + 4 * index
        for rom in (base, japanese):
            if table + int.from_bytes(rom[entry:entry+4], "little") != offset:
                raise ValueError("Resource table mismatch")
    if base[SELECTOR] != 0 or japanese[SELECTOR] != 0x30:
        raise ValueError("Unexpected selector compression header")
    if base[SELECTOR+1:SELECTOR+133] != japanese[SELECTOR+1:SELECTOR+133]:
        raise ValueError("Selector payload differs beyond the type byte")
    splash, used = decompress(japanese, SPLASH[0])
    selector, selector_used = decompress(japanese, SELECTOR)
    if (len(splash), used, len(selector), selector_used) != (1440, 1150, 128, 133):
        raise ValueError("Unexpected resource extents")
    out = bytearray(base)
    out[SPLASH[0]:SPLASH[1]] = japanese[SPLASH[0]:SPLASH[1]]
    out[SELECTOR] = 0x30
    if decompress(out, SPLASH[0])[0] != splash or decompress(out, SELECTOR)[0] != selector:
        raise ValueError("Restored stream roundtrip mismatch")
    # Compare every unowned byte, including EEPROM routines, fonts and header.
    for lo, hi in [(0, SPLASH[0]), (SPLASH[1], SELECTOR), (SELECTOR+1, len(base))]:
        if out[lo:hi] != base[lo:hi]:
            raise ValueError("Write escaped its declared region")
    result = bytes(out)
    return result, {
        "schema": "narikiri2-local-graphics-test-v1", "version": "v0.9d-graphics-test",
        "source_sha256": sha(base), "reference_sha256": sha(japanese),
        "target_sha256": sha(result), "size": len(result),
        "different_bytes": sum(a != b for a, b in zip(base, result)),
        "owned_regions": [
            {"start": hex(SPLASH[0]), "end_exclusive": hex(SPLASH[1]),
             "purpose": "restore original Produced by NAMCO graphics", "decoded_bytes": len(splash)},
            {"start": hex(SELECTOR), "end_exclusive": hex(SELECTOR+1),
             "purpose": "restore formation selector RL type 00 -> 30", "decoded_bytes": len(selector)}],
        "unowned_bytes_unchanged": True,
        "runtime_verification": "separate evidence required",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--japanese", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args()
    base = args.baseline.read_bytes()
    rom, manifest = repair(base, args.japanese.read_bytes())
    patch = create_bps(base, rom, b"Local v0.9d graphics test; exact v0.9c input")
    if apply_bps(base, patch) != rom:
        raise ValueError("BPS roundtrip mismatch")
    args.out_dir.mkdir(parents=True, exist_ok=False)
    (args.out_dir / "NARIKIRI2_v0.9d_graphics_test.gba").write_bytes(rom)
    (args.out_dir / "v09c_to_v09d_graphics_test.bps").write_bytes(patch)
    manifest["bps_sha256"] = sha(patch)
    (args.out_dir / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

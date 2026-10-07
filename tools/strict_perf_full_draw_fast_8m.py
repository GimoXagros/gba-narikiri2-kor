"""Guarded exact 8 MiB diagnostic of native 12-pixel glyph composition."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB

BASE_SHA = 'dc14db5d22f43657d61cd25f9fb672fa122a81b292f7cdf15a869cfa20fa599e'
# Active recompressed font ends at CAA10; original owned resource ends CABC1.
RETIRED_SMALL_FONT_SHA = 'b730a9dfbf01efd4f3d5ad420b3b68b6798f7fb974a5bfa84556c3afcbedfe52'

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "asm/strict_perf_full_draw_fast.s"
SLOT = (0xCAA10, 0xCABC1)
CALLS = (("even", 0x1520, 0x080011C9, 0xCAA10),
         ("odd", 0x150C, 0x08001351, 0xCAA18))


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def assemble(source: str, offset: int) -> bytes:
    return bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source,
                 addr=0x08000000 + offset)[0])


def build(base: bytes) -> tuple[bytes, dict]:
    if len(base) != 0x800000 or sha(base) != BASE_SHA:
        raise ValueError("Frozen exact 8 MiB identity changed")
    if sha(base[SLOT[0]:SLOT[1]]) != RETIRED_SMALL_FONT_SHA:
        raise ValueError("Retired font owner changed")
    code = assemble(SOURCE.read_text(encoding="utf-8"), SLOT[0])
    if len(code) != 328 or len(code) > SLOT[1] - SLOT[0]:
        raise ValueError("Full draw code size/owner changed")
    if code.find(bytes.fromhex("13001cde")) != 4:
        raise ValueError("Odd entry marker moved")
    out = bytearray(base)
    out[SLOT[0]:SLOT[0] + len(code)] = code
    writes = [dict(name="full_draw_code", offset=hex(SLOT[0]), size=len(code),
                   before_sha256=sha(base[SLOT[0]:SLOT[0] + len(code)]),
                   after_sha256=sha(code))]
    for name, call, original, destination in CALLS:
        before = assemble(f"bl {original & ~1}", call)
        if bytes(out[call:call + 4]) != before:
            raise ValueError(name + " native call changed")
        after = assemble(f"bl {0x08000000 + destination}", call)
        out[call:call + 4] = after
        writes.append(dict(name=name + "_draw_call", offset=hex(call), size=4,
                           target=hex(0x08000000 + destination + 1),
                           before_sha256=sha(before), after_sha256=sha(after)))
    return bytes(out), {"status": "FULL_DRAW_FAST_8MIB_DIAGNOSTIC_NOT_PRODUCT",
                        "baseline_sha256": BASE_SHA, "candidate_sha256": sha(out),
                        "size": len(out), "code_bytes": len(code),
                        "code_capacity": SLOT[1] - SLOT[0],
                        "text_pointer_changes": 0, "compressed_stream_changes": 0,
                        "writes": writes}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite diagnostic output")
    image, report = build(args.baseline.read_bytes())
    args.out.mkdir(parents=True)
    (args.out / "FULL_DRAW_FAST_8MIB_DIAGNOSTIC.gba").write_bytes(image)
    (args.out / "BUILD.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("candidate_sha256", "code_bytes")}))


if __name__ == "__main__":
    main()

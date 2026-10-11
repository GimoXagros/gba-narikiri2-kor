"""Build a non-product SELECT_JOB hook diagnostic from the frozen boot PoC.

Only 201 SELECT_JOB entries are strict-encoded. The rest of the adopted Korean
ROM retains its old representation; this output must never be a release input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from strict_runtime_select_job import (TABLE_OFFSET, ROW_COUNT, read_csv, digest)

BOOT_SHA = "81b42453089a58ec125fde4bb8b3caa77609239aaceb5b3e90fec994e6e4e7ef"
STRICT_SHA = "ba9a42690ce2899d9465a41cb326f31f4af6f4cc8047fcb4840f22e0ed3e5006"
BOOK_SHA = "25553331cee20c17c778ac6d63f790c7057b9274b35a8d8ccbb939644bef66d3"
DIAGNOSTIC_SIZE = 13_270_790
TITLE_VENEER_BEFORE = bytes.fromhex("0e009799995901999914009999040099")


def build(boot: bytes, strict: bytes, book: bytes, bindings: list[dict[str, str]],
          fits: list[dict[str, str]], code: bytes, desc: bytes, veneer: bytes,
          call_patch: bytes) -> tuple[bytes, dict]:
    if len(boot) != DIAGNOSTIC_SIZE or digest(boot) != BOOT_SHA:
        raise ValueError("Wrong frozen boot-LZ diagnostic source")
    if len(strict) != 0x800000 or digest(strict) != STRICT_SHA:
        raise ValueError("Wrong frozen strict data image")
    if digest(book) != BOOK_SHA:
        raise ValueError("Wrong frozen compact book")
    if len(code) != 628 or len(desc) != 1608 or len(veneer) != 16 or len(call_patch) != 4:
        raise ValueError("Wrong hook artifact extent")
    result = bytearray(boot)
    writes = []
    def put(start: int, expected: bytes, payload: bytes, label: str) -> None:
        if result[start:start + len(expected)] != expected or len(expected) != len(payload):
            raise ValueError(f"Before bytes differ: {label}")
        result[start:start + len(payload)] = payload
        writes.append({"label": label, "start": f"{start:08X}", "bytes": len(payload),
                       "before_sha256": digest(expected), "after_sha256": digest(payload)})

    fit_by_id = {r["binding_id"]: r for r in fits}
    rows = sorted((r for r in bindings if r["id"].startswith("SELECT_JOB_")),
                  key=lambda r: int(r["id"].split("_")[2]))
    if len(rows) != ROW_COUNT:
        raise ValueError("Missing SELECT_JOB denominator")
    streams = {}
    for i, row in enumerate(rows):
        storage = int(row["jp_pointer_storage"])
        if storage != TABLE_OFFSET + 4 * i:
            raise ValueError("SELECT_JOB table index mismatch")
        expected_pointer = struct.pack("<I", int(row["jp_pointer_value"]))
        if strict[storage:storage + 4] != expected_pointer:
            raise ValueError("Strict image pointer differs from JP source")
        put(storage, bytes(result[storage:storage + 4]), expected_pointer,
            f"SELECT_JOB_{i:03d}_pointer_restore")
        start = int(row["jp_text_start"])
        encoded = int(fit_by_id[row["binding_id"]]["encoded_length"])
        stream = strict[start:start + encoded]
        if start in streams and streams[start] != stream:
            raise ValueError("Shared original start has divergent physical stream")
        streams[start] = stream
    for start, stream in sorted(streams.items()):
        put(start, bytes(result[start:start + len(stream)]), stream,
            f"SELECT_JOB_stream_{start:08X}")
    put(0x1C3B4, bytes.fromhex("e8f7f0fc"), call_patch, "SELECT_JOB_call")
    put(0x37D980, TITLE_VENEER_BEFORE, veneer, "title_suffix_near_veneer")
    for start, payload, label in ((0xC99000, code, "runtime_thumb"),
                                  (0xC99400, desc, "select_descriptors"),
                                  (0xC9A000, book, "compact_book")):
        if not (0xC933C4 <= start and start + len(payload) <= 0xCA3C00):
            raise ValueError("PoC arena placement outside boot-LZ reclaimed area")
        put(start, bytes(result[start:start + len(payload)]), payload, label)
    manifest = {"schema": "select-job-diagnostic-not-product-v1",
                "source_sha256": BOOT_SHA, "source_bytes": len(boot),
                "output_sha256": digest(result), "output_bytes": len(result),
                "select_job_bindings": len(rows), "physical_streams": len(streams),
                "writes": writes, "status": "DIAGNOSTIC_ONLY__GAME_EVENT_NOT_RUN"}
    return bytes(result), manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("boot", "strict", "book", "bindings", "fit", "code",
                 "descriptors", "veneer", "call-patch", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Diagnostic output already exists")
    rom, manifest = build(args.boot.read_bytes(), args.strict.read_bytes(),
                          args.book.read_bytes(), read_csv(args.bindings),
                          read_csv(args.fit), args.code.read_bytes(),
                          args.descriptors.read_bytes(), args.veneer.read_bytes(),
                          args.call_patch.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(rom)
    args.out.with_suffix(".json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "writes"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

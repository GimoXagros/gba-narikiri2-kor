"""Fail-closed fixed-buffer primitives for the AN9J strict-layout experiment.

This module is not an asset placement oracle. Callers must obtain ownership,
consumer closure and source correspondence independently. No append/truncate
operation or automatic pointer conversion is provided.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, Iterable

ROM_SIZE = 0x800000
ROM_BASE = 0x08000000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Binding:
    identity: str
    storage: int
    pointer: bytes
    start: int
    end: int
    expected_output: bytes
    kind: str = "absolute_rom_le32"

    def validate(self, source: bytes) -> None:
        if self.kind != "absolute_rom_le32" or len(self.pointer) != 4:
            raise ValueError(f"{self.identity}: unsupported pointer representation")
        if not (0 <= self.storage <= len(source) - 4
                and 0 <= self.start < self.end <= len(source)):
            raise ValueError(f"{self.identity}: binding outside source")
        if source[self.storage:self.storage + 4] != self.pointer:
            raise ValueError(f"{self.identity}: original pointer bytes changed")
        if int.from_bytes(self.pointer, "little") != ROM_BASE + self.start:
            raise ValueError(f"{self.identity}: pointer/start disagreement")


@dataclass(frozen=True)
class Write:
    writer_id: str
    start: int
    before: bytes
    after: bytes
    purpose: str
    consumer: str
    provenance: str
    tests: tuple[str, ...]

    @property
    def end(self) -> int:
        return self.start + len(self.after)

    def manifest(self) -> dict:
        return dict(writer_id=self.writer_id, start=self.start, end=self.end,
                    before_sha256=sha(self.before), after_sha256=sha(self.after),
                    purpose=self.purpose, consumer=self.consumer,
                    provenance=self.provenance, tests=list(self.tests))


def validate_bindings(source: bytes, bindings: Iterable[Binding]) -> list[Binding]:
    rows = list(bindings)
    if not rows:
        raise ValueError("Empty text-binding denominator")
    identities, by_start = set(), {}
    for row in rows:
        row.validate(source)
        if row.identity in identities:
            raise ValueError(f"Duplicate binding identity: {row.identity}")
        identities.add(row.identity)
        previous = by_start.get(row.start)
        if previous and (previous.end != row.end
                         or previous.expected_output != row.expected_output):
            raise ValueError(f"ALIAS_SEMANTIC_CONFLICT: {previous.identity}, {row.identity}")
        by_start[row.start] = row
    spans = sorted(by_start.values(), key=lambda row: row.start)
    for left, right in zip(spans, spans[1:]):
        if left.end > right.start:
            raise ValueError(f"Unresolved interior alias: {left.identity}, {right.identity}")
    return rows


def slot_write(source: bytes, binding: Binding, stream: bytes,
               *, encoding: str, consumer: str, provenance: str) -> Write:
    binding.validate(source)
    if not stream or len(stream) > binding.end - binding.start:
        raise ValueError(f"{binding.identity}: slot overflow or empty stream")
    # Leave the unused suffix identical to the original; no guessed padding.
    return Write("text:" + binding.identity, binding.start,
                 source[binding.start:binding.start + len(stream)], stream,
                 encoding, consumer, provenance, ("bounded_decode", "slot_fit"))


def assemble_fixed(source: bytes, writes: Iterable[Write],
                   bindings: Iterable[Binding]) -> tuple[bytes, list[dict]]:
    """Write into the immutable source's *existing* 8MiB address space only."""
    if len(source) != ROM_SIZE:
        raise ValueError("Strict source must contain exactly 8MiB")
    rows = validate_bindings(source, bindings)
    ordered = sorted(writes, key=lambda row: (row.start, row.writer_id))
    identifiers, previous_end = set(), 0
    for write in ordered:
        if not write.writer_id or write.writer_id in identifiers:
            raise ValueError("Missing or duplicate writer ID")
        identifiers.add(write.writer_id)
        if not write.after or len(write.before) != len(write.after):
            raise ValueError(f"{write.writer_id}: unequal or empty write")
        if write.start < previous_end or write.start < 0 or write.end > ROM_SIZE:
            raise ValueError(f"{write.writer_id}: overlapping or out-of-range write")
        if not all((write.purpose, write.consumer, write.provenance, write.tests)):
            raise ValueError(f"{write.writer_id}: missing ownership evidence")
        if source[write.start:write.end] != write.before:
            raise ValueError(f"{write.writer_id}: expected source bytes changed")
        for row in rows:
            lo, hi = max(write.start, row.storage), min(write.end, row.storage + 4)
            if lo < hi and write.after[lo-write.start:hi-write.start] != source[lo:hi]:
                raise ValueError(f"{write.writer_id}: protected text pointer {row.identity}")
        previous_end = write.end
    result = bytearray(source)
    for write in ordered:
        # Equal-sized memoryview assignment cannot resize the buffer.
        memoryview(result)[write.start:write.end] = write.after
    cursor = 0
    for write in ordered:
        if result[cursor:write.start] != source[cursor:write.start]:
            raise ValueError("Unowned output difference")
        if result[write.start:write.end] != write.after:
            raise ValueError("Final write mismatch")
        cursor = write.end
    if result[cursor:] != source[cursor:] or len(result) != ROM_SIZE:
        raise ValueError("Final size or untouched suffix changed")
    return bytes(result), [row.manifest() for row in ordered]


def verify_decoded(image: bytes, bindings: Iterable[Binding],
                   decode: Callable[[bytes, int, int, int], bytes]) -> dict:
    """Re-read final streams with exact slot and output bounds.

    Decoder receives (image, start, slot_end, max_output_bytes). Output includes
    the original native termination bytes. This is a content check only;
    it cannot certify unknown consumers or relocation closure.
    """
    if len(image) != ROM_SIZE:
        raise ValueError("Strict image is not exactly 8MiB")
    rows = list(bindings)
    if not rows:
        raise ValueError("Empty verification denominator")
    for row in rows:
        row.validate(image)
        decoded = decode(image, row.start, row.end, len(row.expected_output))
        if decoded != row.expected_output:
            raise ValueError(f"{row.identity}: final translation mismatch")
    return dict(pointer_bindings_total=len(rows), pointer_value_mismatch_count=0,
                text_start_mismatch_count=0, translation_mismatch_count=0,
                scope="CATALOG_CONTENT_ONLY_NOT_RUNTIME_OR_REFERENCE_CLOSURE")

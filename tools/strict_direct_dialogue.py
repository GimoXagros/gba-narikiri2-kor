"""Diagnostic adapter for the direct 0809AA68 -> 0809A43C dialogue route.

This adapter retains decoded bytes on its own stack until the original
dialogue renderer returns. It is not a product integration or a claim that
all dialogue callers are closed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB

ROOT = Path(__file__).resolve().parents[1]
ENTRY = 0x9A43C
WRAPPER = 0xCAB58
TRAMPOLINE = 0xCA3A8
WRAPPER_CAPACITY = 105
TRAMPOLINE_CAPACITY = 76
JAPANESE_SHA256 = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
GUARDED_SHA256 = "d31150acad4e9bd92ed8c22776028c561ebb9317688b20fca68843b960f2ff21"


def assemble(japanese: bytes, guarded: bytes) -> tuple[tuple[int, bytes], ...]:
    """Return guarded offset/bytes pairs; refuse changed original entry."""
    if len(japanese) != 0x800000 or len(guarded) != 0x800000:
        raise ValueError("Exact 8 MiB inputs required")
    from strict_owned_decode import assemble_sync_wrapper
    from strict_format_hook import dialogue_veneer

    original = japanese[ENTRY:ENTRY + 20]
    if guarded[ENTRY:ENTRY + 20] != original:
        raise ValueError("Direct dialogue original prologue differs")
    if guarded[WRAPPER:WRAPPER + WRAPPER_CAPACITY] != bytes(WRAPPER_CAPACITY):
        raise ValueError("Wrapper owner is not the cleared retired font suffix")
    if guarded[TRAMPOLINE:TRAMPOLINE + TRAMPOLINE_CAPACITY] != japanese[TRAMPOLINE:TRAMPOLINE + TRAMPOLINE_CAPACITY]:
        raise ValueError("Trampoline owner is not the original free suffix")

    wrapper = assemble_sync_wrapper(
        0x08000000 + WRAPPER,
        decoder=0x080B9C01,
        source_register=0,
        consumer=0x08000000 + TRAMPOLINE + 1,
        fail_stop=0x080B9DE5,
        caller_buffer=True,
    )
    source = """
    push {r4-r7,lr}
    mov r7,sl
    mov r6,sb
    mov r5,r8
    push {r5-r7}
    sub sp,#72
    str r0,[sp,#36]
    str r1,[sp,#40]
    str r2,[sp,#44]
    str r3,[sp,#48]
    ldr r3,target
    bx r3
    .balign 4,0
target: .word 0x0809A451
"""
    trampoline = bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source, addr=0x08000000 + TRAMPOLINE)[0])
    veneer = dialogue_veneer(0x08000000 + ENTRY, 0x08000000 + WRAPPER)
    if len(wrapper) > WRAPPER_CAPACITY or len(trampoline) > TRAMPOLINE_CAPACITY or len(veneer) != 16:
        raise ValueError("Adapter exceeds proved owners")
    return ((WRAPPER, wrapper), (TRAMPOLINE, trampoline), (ENTRY, veneer))


def diagnostic_patch(japanese: bytes, guarded: bytes) -> tuple[bytes, dict]:
    if hashlib.sha256(japanese).hexdigest() != JAPANESE_SHA256:
        raise ValueError("Exact Japanese source required")
    if hashlib.sha256(guarded).hexdigest() != GUARDED_SHA256:
        raise ValueError("Exact guarded diagnostic required")
    writes = assemble(japanese, guarded)
    result = bytearray(guarded)
    for offset, payload in writes:
        result[offset:offset + len(payload)] = payload
    evidence = {
        "status": "DIAGNOSTIC_ONLY_DIRECT_DIALOGUE_ADAPTER",
        "input_sha256": hashlib.sha256(guarded).hexdigest(),
        "output_sha256": hashlib.sha256(result).hexdigest(),
        "size": len(result),
        "writes": [{"offset": offset, "bytes": len(payload), "before_sha256": hashlib.sha256(guarded[offset:offset+len(payload)]).hexdigest(), "after_sha256": hashlib.sha256(payload).hexdigest()} for offset, payload in writes],
    }
    return bytes(result), evidence

"""Diagnostic-only fix for a compressed ARTE description's length consumer.

The original description renderer at 0x08013DE4 already receives native text
through the owned formatter hook. Its second lookup at 0x08013DEA is instead
passed directly to strlen. Decode that pointer into a caller-owned stack buffer
for the duration of strlen, preserving the native byte-count and branch.
"""
from __future__ import annotations

import hashlib

from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB


JAPANESE_SHA256 = "a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7"
INPUT_SHA256 = "3abc759d104e2edee4db63e2f4ec7eb18d5e870f1e0c20d070656c5b6a72680f"
LENGTH_CALL = 0x13DEE
HELPER = 0xCA3C4
HELPER_END = 0xCA3F4
ORIGINAL_CALL = bytes.fromhex("92f0f5fe")  # BL 0x080A6BDC


def assemble() -> tuple[bytes, bytes]:
    """Assemble the fixed-address helper and call without modifying an image."""
    source = """
    push {r4,lr}
    sub sp,#288
    mov r1,sp
    movs r2,#144
    lsls r2,r2,#1
    ldr r3,owned
    bl call_r3
    cmp r0,#0
    beq failed
    ldr r3,native_strlen
    bl call_r3
    add sp,#288
    pop {r4,pc}
failed:
    ldr r3,stop
call_r3:
    bx r3
    .align 2
owned: .word 0x080B9C01
native_strlen: .word 0x080A6BDD
stop: .word 0x080B9DE5
"""
    ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
    helper = bytes(ks.asm(source, addr=0x08000000 + HELPER)[0])
    call = bytes(ks.asm(f"bl #0x{0x08000000 + HELPER:08x}", addr=0x08000000 + LENGTH_CALL)[0])
    if len(helper) != HELPER_END - HELPER or len(call) != 4:
        raise ValueError("Length adapter does not fit its proved owner")
    return helper, call


def diagnostic_patch(japanese: bytes, candidate: bytes) -> tuple[bytes, dict]:
    if len(japanese) != 0x800000 or hashlib.sha256(japanese).hexdigest() != JAPANESE_SHA256:
        raise ValueError("Exact 8 MiB Japanese source required")
    if len(candidate) != 0x800000 or hashlib.sha256(candidate).hexdigest() != INPUT_SHA256:
        raise ValueError("Exact 8 MiB direct-dialogue candidate required")
    if candidate[LENGTH_CALL:LENGTH_CALL + 4] != ORIGINAL_CALL:
        raise ValueError("Native strlen call no longer matches")
    if candidate[HELPER:HELPER_END] != japanese[HELPER:HELPER_END]:
        raise ValueError("Former font suffix owner differs from source")
    helper, call = assemble()
    out = bytearray(candidate)
    out[HELPER:HELPER_END] = helper
    out[LENGTH_CALL:LENGTH_CALL + 4] = call
    evidence = {
        "status": "DIAGNOSTIC_ONLY_ARTE_DESCRIPTION_LENGTH_ADAPTER",
        "input_sha256": INPUT_SHA256,
        "output_sha256": hashlib.sha256(out).hexdigest(),
        "size": len(out),
        "writes": [
            {"offset": HELPER, "bytes": len(helper), "before_sha256": hashlib.sha256(candidate[HELPER:HELPER_END]).hexdigest(), "after_sha256": hashlib.sha256(helper).hexdigest()},
            {"offset": LENGTH_CALL, "bytes": len(call), "before_hex": ORIGINAL_CALL.hex(), "after_hex": call.hex()},
        ],
    }
    return bytes(out), evidence

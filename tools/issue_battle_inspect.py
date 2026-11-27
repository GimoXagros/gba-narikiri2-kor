"""Decode the enemy-info inputs before the existing affine tile renderer."""

from hashlib import sha256

from strict_compact_font import validate_thumb


ENTRY = 0x25FDC
NATIVE_BODY_LIMIT = 0x26010
RENDERER = 0x080C5AC0
BUFFER_BYTES = 64
GUARDS = (
    (0x25F0C, ENTRY, "3147211e9e43628fcf5c2e025d149152d227a02cacf5c6c52b985ac00355a871"),
    (ENTRY, NATIVE_BODY_LIMIT, "3836edd9f9b75ef5ca73382356a4ab22044507bf523ab6cc5fc8d7e5ab034f92"),
    (RENDERER - 0x08000000, 0xC5BA8, "795b635bca2e2a9438095ba60dee398338cb00fc5842bbf45fc717f149c84da0"),
)


def assemble():
    from keystone import KS_ARCH_ARM, KS_MODE_THUMB, Ks

    # The native body is dormant after v0.9a's entry veneer. All eight
    # inspection calls target ENTRY, so the wrapper reuses its prefix.
    # A row has at most 15 cells, each taking up to three compact bytes.
    # The owned decoder returns native RAM (HP and icon text) unchanged.
    source = f"""
        push {{r0,r1,r4,lr}}
        sub sp, #{BUFFER_BYTES}
        movs r0, r2
        mov r1, sp
        movs r2, #{BUFFER_BYTES}
        ldr r3, decoder
        bl call_r3
        cmp r0, #0
        beq done
        movs r2, r0
        add r3, sp, #{BUFFER_BYTES}
        ldmia r3!, {{r0,r1}}
        ldr r3, renderer
        bl call_r3
    done:
        add sp, #{BUFFER_BYTES + 8}
        pop {{r4,pc}}
    call_r3:
        bx r3
        .balign 4,0
    decoder: .word 0x080B9C01
    renderer: .word {RENDERER | 1}
    """
    code, _ = Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source, addr=0x08000000 + ENTRY)
    payload = bytes(code)
    validate_thumb(payload, 2)
    if len(payload) > NATIVE_BODY_LIMIT - ENTRY:
        raise ValueError("Inspection decoder wrapper exceeds the original function prefix")
    return payload


def fix_battle_inspection(image):
    """Reuse the original inspection entry and keep its affine renderer intact."""
    if len(image) != 0x800000:
        raise ValueError("Battle inspection requires an 8 MiB ROM")
    for start, end, expected in GUARDS:
        if sha256(image[start:end]).hexdigest() != expected:
            raise ValueError(f"Unexpected battle inspection code at {start:#x}")
    payload = assemble()
    end = ENTRY + len(payload)
    result = bytearray(image)
    result[ENTRY:end] = payload
    return bytes(result), [dict(
        owner="battle_inspection_decoder", offset=ENTRY, end=end,
        before_sha256=sha256(image[ENTRY:end]).hexdigest(),
        after_sha256=sha256(payload).hexdigest(),
    )]

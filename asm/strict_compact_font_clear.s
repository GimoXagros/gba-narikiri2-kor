/* Retain direct clear-bank access. Only palette 11 needs a local solid tile.
 * The synchronous tile cache compares/copies all 32 bytes before returning.
 * Exact source validation proves each clear nibble is 0/F, so OR B is lossless.
 */
    push {r1, r2, r3, lr}
    ldr r3, decoder
    bl call_r3
    adds r1, r0, #1
    beq done
    lsls r0, r0, #5
    ldr r1, palette_mode
    ldrb r1, [r1]
    cmp r1, #11
    beq solid
    ldr r1, clear_font
    b get
solid:
    push {r4, r5}
    sub sp, #32
    ldr r1, clear_font
    adds r0, r0, r1
    mov r1, sp
    movs r2, #8
    ldr r4, solid_bits
make_solid:
    ldmia r0!, {r3}
    orrs r3, r4
    stmia r1!, {r3}
    subs r2, #1
    bne make_solid
    mov r0, sp
    ldr r3, cache
    bl call_r3
    add sp, #32
    pop {r4, r5}
    b done
get:
    adds r0, r0, r1
    ldr r3, cache
    bl call_r3
done:
    pop {r1, r2, r3}
    pop {r3}
    bx r3
call_r3:
    bx r3
    .balign 4, 0
decoder: .word BANKED_DECODER
cache: .word TILE_CACHE
palette_mode: .word 0x0300145a
clear_font: .word CLEAR_FONT
solid_bits: .word 0xbbbbbbbb

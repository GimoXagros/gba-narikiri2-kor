/* Already validated wrapping text and profile: reuse the proven fused label
 * compositor only for glyphs separated by singleton lexical halfspaces.
 * Whole-buffer proof precedes any private-buffer mutation. */
    push {r4-r6,lr}
    movs r4,r0
    movs r5,r1
    movs r6,r2
    movs r3,#0
scan:
    ldrb r0,[r1]
    adds r1,#1
    cmp r0,#0
    beq proved
    cmp r0,#127
    beq glyph
    cmp r0,#31
    bne general
    cmp r3,#0
    beq general
    movs r3,#0
    b scan
glyph:
    adds r1,#2
    movs r3,#1
    b scan
proved:
    cmp r3,#0
    beq general
    movs r1,r5
rewrite:
    ldrb r0,[r1]
    cmp r0,#0
    beq fused
    cmp r0,#127
    bne space
    adds r1,#3
    b rewrite
space:
    movs r0,#32
    strb r0,[r1]
    adds r1,#1
    b rewrite
fused:
    movs r0,r4
    movs r1,r5
    movs r2,r6
    bl 0x08002264
    b done
general:
    movs r0,r4
    movs r1,r5
    movs r2,r6
    movs r3,#0
    bl NORMAL_DRAW
done:
    pop {r4-r6}
    pop {r3}
    bx r3

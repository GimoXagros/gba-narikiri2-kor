/* Already validated marker-free buffer: batch at least five pure Hangul glyphs.
 * Short labels retain native lookup: batch setup costs more than it saves.
 * ASCII, spaces, controls and unsupported geometry retain the native path. */
    push {r4-r6,lr}
    movs r4,r0
    movs r5,r1
    movs r6,#0
scan:
    ldrb r0,[r1]
    cmp r0,#0
    beq proved
    cmp r0,#127
    bne bad
    adds r1,#3
    adds r6,#1
    b scan
proved:
    cmp r6,#5
    blo bad
    movs r0,r4
    bl NORMAL_RENDER_GATE
    cmp r0,#0
    beq bad
    movs r2,r1
    movs r0,r4
    movs r1,r5
    bl 0x08002264
    movs r0,#1
    b done
bad:
    movs r0,#0
done:
    pop {r4-r6}
    pop {r3}
    bx r3

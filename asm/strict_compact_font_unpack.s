/* r0 glyph index, r1 caller-owned 32-byte tile, r2 mode 0/1.
 * Return destination, or zero for invalid index/mode/alignment. No globals.
 * Caller proves 32 writable bytes and non-overlap with immutable font/tables.
 */
    push {r4-r7,lr}
    ldr r3, glyph_count
    cmp r0,r3
    bhs invalid
    cmp r2,#1
    bhi invalid
    movs r3,#1
    tst r1,r3
    bne invalid
    movs r6,r1
    lsls r0,r0,#3
    ldr r4, font
    adds r4,r4,r0
    lsls r2,r2,#5
    ldr r5, nibble_tables
    adds r5,r5,r2
    movs r7,#8
row:
    ldrb r0,[r4]
    movs r2,#15
    ands r2,r0
    lsls r2,r2,#1
    ldrh r2,[r5,r2]
    strh r2,[r6]
    lsrs r0,r0,#4
    lsls r0,r0,#1
    ldrh r0,[r5,r0]
    strh r0,[r6,#2]
    adds r4,#1
    adds r6,#4
    subs r7,#1
    bne row
    movs r0,r1
    b finish
invalid:
    movs r0,#0
finish:
    pop {r4-r7}
    pop {r3}
    bx r3
    .balign 4,0
glyph_count: .word FONT_COUNT
font: .word FONT_BITS
nibble_tables: .word FONT_NIBBLES

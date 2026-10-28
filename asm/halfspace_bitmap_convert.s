/* Entry21FC from the existing B9560 wrapper: glyph32B is at SP+20.
 * Convert only the native12 columns; preserve the rightmost4 destination pixels.
 * The wrapper restores R0 and owns the stacked R4-R7/return address.
 */
bitmap_convert:
    mov r5,r0
    mov r6,r0
    adds r6,#32
    add r4,sp,#20
    ldr r3,bitmap_lut_ptr
    movs r7,#16
bitmap_row:
    ldrh r0,[r4]
    lsls r1,r0,#28
    lsrs r1,r1,#27
    ldrh r1,[r3,r1]
    lsrs r2,r0,#4
    lsls r2,r2,#28
    lsrs r2,r2,#27
    ldrh r2,[r3,r2]
    lsls r2,r2,#16
    orrs r1,r2
    str r1,[r5]
    lsrs r0,r0,#8
    lsls r0,r0,#28
    lsrs r0,r0,#27
    ldrh r0,[r3,r0]
    strh r0,[r6]
    adds r4,#2
    adds r5,#4
    adds r6,#4
    subs r7,#1
    cmp r7,#8
    bne bitmap_no_jump
    adds r5,#32
    adds r6,#32
bitmap_no_jump:
    cmp r7,#0
    bne bitmap_row
    pop {r4-r7,pc}
    .balign 4,0
bitmap_lut_ptr: .word bitmap_lut
bitmap_lut:
    .hword 0x0000,0x000f,0x00f0,0x00ff
    .hword 0x0f00,0x0f0f,0x0ff0,0x0fff
    .hword 0xf000,0xf00f,0xf0f0,0xf0ff
    .hword 0xff00,0xff0f,0xfff0,0xffff

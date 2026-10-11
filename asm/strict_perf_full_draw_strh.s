/* Exact 12-pixel 1bpp-to-4bpp full-font compositor, Thumb-1/ARM7TDMI.
 * The caller owns the decoded 32-byte glyph and destination. The native
 * background byte is used only when it is a nibble; unusual values tail-call
 * the original renderer with the original arguments and LR.
 */
fast_even:
    movs r2,#0
    b start
    .balign 4,0
odd_marker: .word 0xde1c0013
fast_odd:
    movs r2,#1
    b start
start:
    push {r4-r7,lr}
    sub sp,#8
    str r2,[sp,#4]
    mov r5,r0
    mov r6,r0
    adds r6,#32
    mov r4,r1
    mov r0,r12
    str r0,[sp]
    ldr r0,background
    ldrb r0,[r0]
    cmp r0,#15
    bhi fallback
    mov r7,r0
    lsls r0,r0,#4
    orrs r7,r0
    mov r0,r7
    lsls r0,r0,#8
    orrs r7,r0
    mov r0,r7
    lsls r0,r0,#16
    orrs r7,r0
    ldr r3,lut_ptr
    movs r0,#16
    mov r12,r0
    ldr r0,[sp,#4]
    cmp r0,#0
    beq even_loop
    b odd_loop

even_loop:
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
    orrs r1,r7
    str r1,[r5]
    lsrs r0,r0,#8
    lsls r0,r0,#28
    lsrs r0,r0,#27
    ldrh r0,[r3,r0]
    orrs r0,r7
    strh r0,[r6]
    adds r4,#2
    adds r5,#4
    adds r6,#4
    mov r1,r12
    subs r1,#1
    mov r12,r1
    cmp r1,#8
    bne even_no_jump
    ldr r0,next_tile_row
    adds r5,r5,r0
    adds r6,r6,r0
even_no_jump:
    cmp r1,#0
    bne even_loop
    b done

odd_loop:
    ldrh r0,[r4]
    lsls r1,r0,#28
    lsrs r1,r1,#27
    ldrh r1,[r3,r1]
    orrs r1,r7
    strh r1,[r5,#2]
    lsrs r1,r0,#4
    lsls r1,r1,#28
    lsrs r1,r1,#27
    ldrh r1,[r3,r1]
    lsrs r0,r0,#8
    lsls r0,r0,#28
    lsrs r0,r0,#27
    ldrh r0,[r3,r0]
    lsls r0,r0,#16
    orrs r0,r1
    orrs r0,r7
    str r0,[r6]
    adds r4,#2
    adds r5,#4
    adds r6,#4
    mov r1,r12
    subs r1,#1
    mov r12,r1
    cmp r1,#8
    bne odd_no_jump
    ldr r0,next_tile_row
    adds r5,r5,r0
    adds r6,r6,r0
odd_no_jump:
    cmp r1,#0
    bne odd_loop
done:
    ldr r0,[sp]
    mov r12,r0
    add sp,#8
    pop {r4-r7,pc}

fallback:
    ldr r0,[sp]
    mov r12,r0
    mov r0,r5
    mov r1,r4
    ldr r2,[sp,#4]
    cmp r2,#0
    beq fallback_even
    ldr r3,original_odd
    b fallback_call
fallback_even:
    ldr r3,original_even
fallback_call:
    add sp,#8
    pop {r4-r7}
    pop {r2}
    mov lr,r2
    bx r3

    .balign 4,0
background: .word 0x0300145a
lut_ptr: .word lut
next_tile_row: .word 0x3a0
original_even: .word 0x080011c9
original_odd: .word 0x08001351
lut:
    .hword 0x0000,0x000f,0x00f0,0x00ff
    .hword 0x0f00,0x0f0f,0x0ff0,0x0fff
    .hword 0xf000,0xf00f,0xf0f0,0xf0ff
    .hword 0xff00,0xff0f,0xfff0,0xffff

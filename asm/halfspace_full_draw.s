/* Native full-window IWRAM compositor: 12px glyphs, reserved 6px spaces.
 * Word and halfword writes are used only at their natural alignments.
 */
even:
    movs r2,#0
    b start
    .balign 4,0
    .word 0xde1c0013
odd:
    movs r2,#4
start:
    ldr r3,window
    ldrb r3,[r3,#6]
    cmp r3,#0
    bne general
    ldr r3,background
    ldrb r3,[r3]
    cmp r3,#15
    bhi general
    ldr r3,aligned_fast
    bx r3
general:
    push {r4-r7,lr}
    sub sp,#12
    mov r4,r0
    mov r0,r12
    str r0,[sp,#8]
    mov r5,r1
    ldr r0,window
    ldrb r1,[r0,#6]
    movs r3,#1
    tst r1,r3
    beq no_half
    adds r2,#6
no_half:
    cmp r2,#8
    blo have_tile
    adds r4,#32
    subs r2,#8
have_tile:
    lsrs r2,r2,#1
    adds r4,r4,r2
    movs r3,#3
    movs r2,#2
    tst r1,r2
    beq have_width
    movs r3,#0
have_width:
    str r3,[sp,#4]
    ldr r0,background
    ldrb r0,[r0]
    movs r1,#15
    ands r0,r1
    lsls r1,r0,#4
    orrs r0,r1
    lsls r7,r0,#8
    orrs r7,r0
    movs r0,#16
    str r0,[sp]
    ldr r3,lut
row:
    mov r0,r4
    ldr r2,[sp,#4]
    cmp r2,#0
    beq space_row
    ldrh r6,[r5]
    lsls r1,r4,#31
    bne unaligned
aligned:
    lsls r1,r6,#28
    lsrs r1,r1,#27
    ldrh r1,[r3,r1]
    orrs r1,r7
    strh r1,[r0]
    adds r0,#2
    lsls r1,r0,#30
    bne aligned_no_jump
    adds r0,#28
aligned_no_jump:
    lsrs r6,r6,#4
    subs r2,#1
    bne aligned
    b row_done
unaligned:
    lsls r1,r6,#28
    lsrs r1,r1,#27
    ldrh r1,[r3,r1]
    orrs r1,r7
    strb r1,[r0]
    lsrs r1,r1,#8
    adds r0,#1
    mov r12,r1
    lsls r1,r0,#30
    bne unaligned_no_jump
    adds r0,#28
unaligned_no_jump:
    mov r1,r12
    strb r1,[r0]
    adds r0,#1
    lsrs r6,r6,#4
    subs r2,#1
    bne unaligned
    b row_done
space_row:
    movs r2,#3
space_pair:
    strb r7,[r0]
    adds r0,#1
    lsls r1,r0,#30
    bne space_no_jump
    adds r0,#28
space_no_jump:
    subs r2,#1
    bne space_pair
row_done:
    adds r5,#2
    adds r4,#4
    ldr r1,[sp]
    subs r1,#1
    str r1,[sp]
    cmp r1,#8
    bne no_jump
    ldr r0,row_jump
    adds r4,r4,r0
no_jump:
    cmp r1,#0
    bne row
    ldr r0,[sp,#8]
    mov r12,r0
    add sp,#12
    pop {r4-r7,pc}
    .balign 4,0
window: .word 0x03000040
background: .word 0x0300145a
row_jump: .word 0x3a0
lut: .word SHARED_LUT
aligned_fast: .word ALIGNED_FAST
sprite_descriptor:
    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
sprite_descriptor_entry_table: .word sprite_descriptor

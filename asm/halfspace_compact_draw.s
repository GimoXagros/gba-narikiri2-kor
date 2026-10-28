/* Display-only leaf for a complete, caller-gated compact label.
 * r0=descriptor, r1=validated native label, r2=palette profile0/11.
 * Dispatcher validates source, caller, controls, spacing and profile first.
 * Pending half tiles live only in this frame.
 * Caller must reset X after this complete-label call; returned X is ceil(px/8).
 */
    push {r4-r7,lr}
    sub sp,#92
    mov r3,r8
    str r3,[sp,#64]
    add r3,sp,#68
    mov r8,r3
    adds r4,r0,#0
    adds r5,r1,#0
    adds r7,r2,#0
    movs r6,#0
    bl BATCH_INIT
    cmp r7,#0
    beq loop
    ldr r7,solid_half
loop:
    ldrb r0,[r5]
    cmp r0,#0
    beq finish
    cmp r0,#32
    beq space
    cmp r6,#0
    beq aligned
    ldrb r0,[r4,#4]
    adds r0,#1
    ldrb r1,[r4,#2]
    cmp r0,r1
    blo shifted
    bl flush
    movs r6,#0
aligned:
    adds r0,r4,#0
    bl WRAP_DIRECT
    adds r0,r5,#0
    bl GET_TILE_DIRECT
    bl store
glyph_next:
    adds r5,#3
    b loop
shifted:
    ldrb r0,[r5,#1]
    lsls r1,r0,#5
    subs r1,r1,r0
    ldrb r0,[r5,#2]
    adds r1,r1,r0
    subs r1,#32
    lsls r1,r1,#5
    ldr r0,font
    adds r1,r1,r0
    /* Font32B and this bounded stack frame are4aligned. One word load
     * resolves both halves; the upper clear half is constant per label. */
    push {r4,r5}
    add r0,sp,#8
    add r2,sp,#40
    lsls r5,r7,#16
    movs r6,#8
join_row:
    ldr r3,[r1]
    orrs r3,r7
    ldrh r4,[r0]
    strh r4,[r2]
    strh r3,[r2,#2]
    lsrs r3,#16
    orrs r3,r5
    str r3,[r0]
    adds r0,#4
    adds r1,#4
    adds r2,#4
    subs r6,#1
    bne join_row
    pop {r4,r5}
    movs r6,#1
    add r0,sp,#32
    bl CACHE_DIRECT
    bl store
    b glyph_next
space:
    cmp r6,#0
    bne space_flush
    adds r0,r4,#0
    bl WRAP_DIRECT
    mov r0,sp
    mov r1,r7
    mov r2,r7
    mov r3,r7
    mov r6,r7
    stmia r0!,{r1-r3,r6}
    stmia r0!,{r1-r3,r6}
    movs r6,#1
    b space_next
space_flush:
    bl flush
    movs r6,#0
space_next:
    adds r5,#1
    b loop
finish:
    cmp r6,#0
    beq done
    bl flush
done:
    ldr r1,dirty
    movs r0,#1
    strb r0,[r1]
    ldr r3,[sp,#64]
    mov r8,r3
    add sp,#92
    pop {r4-r7,pc}
flush:
    push {lr}
    add r0,sp,#4
    bl CACHE_DIRECT
    bl store
    pop {pc}
store:
    adds r1,r0,#1
    beq fatal
    movs r1,#4
    ldrsb r1,[r4,r1]
    lsls r1,r1,#1
    movs r2,#5
    ldrsb r2,[r4,r2]
    lsls r2,r2,#6
    adds r1,r1,r2
    ldr r2,shadow
    adds r1,r1,r2
    ldrb r2,[r4,#7]
    lsls r2,r2,#12
    orrs r0,r2
    strh r0,[r1]
    ldrb r0,[r4,#4]
    adds r0,#1
    strb r0,[r4,#4]
    bx lr
fatal:
    ldr r3,stop
    bx r3
    mov r8,r8
    .balign 4,0
solid_half: .word 0xbbbbbbbb
font: .word COMPACT_FONT
stop: .word DIAGNOSTIC_STOP
shadow: .word 0x03000058
dirty: .word 0x03001459
/* Fixed288byte prefix; wrapped XY changes invalidate this call's pins. */
finish_dispatch:
    cmp r6,#0
    beq original
    ldrb r0,[r5,#6]
    cmp r0,#1
    bne original
    adds r2,r7,#0
    cmp r2,#0
    beq validated_profile
    cmp r2,#11
    bne original
validated_profile:
    adds r0,r4,#0
    bl VALIDATE_LABEL
    bne original
    adds r0,r5,#0
    adds r1,r4,#0
    bl COMPACT_DRAW
    pop {r4-r7,pc}
original:
    adds r0,r5,#0
    adds r1,r4,#0
    bl 0x08001ac8
    pop {r4-r7,pc}

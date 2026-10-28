/* Validated private string only: descriptor, source, clear0/11, nowrap0/1.
 * r8 owns bitmap20/pending32/glyph32/complete32/nowrap4/pad8/saved-r8.
 */
    push {r4-r7,lr}
    sub sp,#132
    mov r4,r8
    str r4,[sp,#128]
    mov r8,sp
    movs r4,r0
    movs r5,r1
    str r3,[sp,#116]
    movs r7,#0
    cmp r2,#0
    beq ready
    ldr r7,solid
ready:
    movs r6,#0
    bl BATCH_INIT
    bl NORMAL_LOOP
    ldr r1,dirty
    movs r0,#1
    strb r0,[r1]
    ldr r3,[sp,#128]
    mov r8,r3
    add sp,#132
    pop {r4-r7}
    pop {r3}
    bx r3
    .balign 4,0
solid: .word 0xbbbbbbbb
dirty: .word 0x03001459

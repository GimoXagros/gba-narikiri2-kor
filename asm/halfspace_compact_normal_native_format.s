/* Original formatter body with direct original small-printer fallback. */
    push {r4,r5,lr}
    movs r5,r0
    adds r2,#4
    ldr r4,buffer
    movs r0,r4
    bl 0x08002648
    movs r0,r5
    movs r1,r4
    bl 0x080b9f14
    pop {r4,r5}
    pop {r0}
    bx r0
    .balign 4,0
buffer: .word 0x03001460

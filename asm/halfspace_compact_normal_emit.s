    push {lr}
    cmp r6,#0
    bne shifted
    adds r2,r1,#1
    beq cache
    movs r0,r1
    b store
shifted:
    movs r1,r0
    mov r0,r8
    adds r0,#20
    mov r2,r8
    adds r2,#84
    movs r3,r7
    bl NORMAL_PAIR
    mov r0,r8
    adds r0,#84
cache:
    bl BATCH_LOOKUP
store:
    bl NORMAL_STORE
    pop {pc}

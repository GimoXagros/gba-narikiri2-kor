    push {lr}
    cmp r6,#0
    beq done
    mov r0,r8
    adds r0,#20
    bl BATCH_LOOKUP
    bl NORMAL_STORE
done:
    pop {pc}

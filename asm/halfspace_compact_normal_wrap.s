    push {lr}
    mov r0,r8
    ldr r0,[r0,#116]
    cmp r0,#0
    bne done
    adds r0,r4,#0
    bl BATCH_WRAP
done:
    pop {pc}

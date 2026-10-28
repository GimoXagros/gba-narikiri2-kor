    push {r4,r5,lr}
    movs r4,r0
    movs r5,r1
    bl NORMAL_PREPARE
    cmp r0,#0
    bne done
    ldr r0,bare
    cmp r4,r0
    beq copy
    adds r0,#4
    cmp r4,r0
    bne bad
copy:
    movs r0,r4
    movs r1,r5
    bl NORMAL_COPY_ARGUMENT
    b done
bad:
    movs r0,#0
done:
    pop {r4,r5}
    pop {r3}
    bx r3
    .balign 4,0
bare: .word 0x082c1da0

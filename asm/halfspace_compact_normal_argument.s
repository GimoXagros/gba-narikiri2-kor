    push {r4,r5,lr}
    movs r5,r1
    bl 0x080c59c0
    movs r4,r0
    movs r1,r5
    movs r2,#64
    bl NORMAL_PREPARE
    cmp r0,#0
    bne done
    lsrs r0,r4,#24
    cmp r0,#2
    beq copy
    cmp r0,#3
    bne bad
copy:
    movs r0,r4
    movs r1,r5
    bl NORMAL_COPY_ARGUMENT
    cmp r0,#0
    beq done
    movs r0,r5
    movs r1,#64
    movs r2,#1
    bl NORMAL_VALIDATE
    cmp r0,#0
    beq done
    cmp r1,#0
    bne bad
    movs r0,r5
    b done
bad:
    movs r0,#0
done:
    pop {r4,r5}
    pop {r3}
    bx r3

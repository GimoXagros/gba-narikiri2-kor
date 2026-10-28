    movs r0,r7
    movs r1,#160
    movs r2,#0
    bl NORMAL_VALIDATE
    cmp r0,#0
    beq fallback
    cmp r1,#0
    beq native
    movs r0,r4
    bl NORMAL_RENDER_GATE
    cmp r0,#0
    beq fallback
    movs r2,r1
    movs r0,r4
    movs r1,r7
    movs r3,#0
    bl NORMAL_LABEL_DRAW
    b done
native:
    movs r0,r4
    movs r1,r7
    bl NORMAL_PLAIN_LABEL
    cmp r0,#0
    bne done
    movs r0,r4
    movs r1,r7
    bl 0x080c5a3c
    b done
fallback:
    movs r0,r4
    movs r1,r5
    movs r2,r6
    bl NORMAL_NATIVE_FORMAT
done:
    add sp,#320
    pop {r4-r7}
    pop {r3}
    bx r3

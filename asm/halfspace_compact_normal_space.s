    push {lr}
    cmp r6,#0
    bne complete
    bl NORMAL_WRAP
    mov r0,r8
    adds r0,#20
    movs r1,r7
    movs r2,r7
    movs r3,r7
    movs r6,r7
    stmia r0!,{r1-r3,r6}
    stmia r0!,{r1-r3,r6}
    movs r6,#1
    b done
complete:
    bl NORMAL_FLUSH
    movs r6,#0
done:
    pop {pc}

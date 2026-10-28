/* Exact relative-slot bounds precede every stack bitmap update. */
mark_returned:
    push {r0,lr}
    mov r3,r8
    ldr r2,[r3,#12]
    adds r1,r2,#1
    cmp r1,#1
    bls done
    subs r2,r0,r2
    ldr r1,[r3,#16]
    cmp r2,r1
    bhs done
    movs r1,#1
    negs r0,r2
    rors r1,r0
    lsrs r2,#5
    lsls r2,#2
    ldr r0,[r3,r2]
    orrs r0,r1
    str r0,[r3,r2]
done:
    pop {r0,pc}

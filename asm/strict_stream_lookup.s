/* Immutable sorted descriptor lookup, ARM7TDMI.
 * r0 absolute stream start; r1 aligned word table; r2 count.
 * Each word: low 23 bits = original ROM offset, high 9 = input slot bytes.
 * Return r0 input bound or zero if this exact start is not registered.
 * Table storage/lifetime is established by the fixed write plan, not guessed
 * by this routine. No text bytes or first-byte heuristics are inspected.
 */
    push {r4-r7,lr}
    movs r4,r1
    movs r5,#0
    movs r6,r2
    lsrs r1,r0,#23
    cmp r1,#16
    bne absent
    lsls r7,r0,#9
    lsrs r7,r7,#9
search:
    cmp r5,r6
    bhs absent
    subs r0,r6,r5
    lsrs r0,r0,#1
    adds r0,r0,r5
    lsls r1,r0,#2
    ldr r3,[r4,r1]
    lsls r2,r3,#9
    lsrs r2,r2,#9
    cmp r2,r7
    beq found
    blo higher
    movs r6,r0
    b search
higher:
    adds r5,r0,#1
    b search
found:
    lsrs r0,r3,#23
    b finish
absent:
    movs r0,#0
finish:
    pop {r4-r7}
    pop {r1}
    bx r1

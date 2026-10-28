/* r0=original source,r1=private capacity>=64 buffer,r2=capacity.
 * Returns copy r0 and exact bytes r1, or zero. No pointer escapes its owner.
 */
    push {r4-r6,lr}
    movs r4,r0
    movs r5,r1
    movs r6,r2
    bl SOURCE_GATE
    cmp r0,#0
    beq bad
    movs r0,r4
    movs r1,r5
    movs r2,r6
    bl 0x080b9c00
    cmp r0,#0
    beq bad
    movs r6,r2
    movs r0,r5
    movs r1,r6
    bl MARK_COPY
    cmp r0,#0
    beq bad
    movs r0,r5
    movs r1,r6
    movs r2,r4
    bl NUMERIC_COPY
    cmp r0,#0
    beq bad
    movs r0,r5
    b done
bad:
    movs r0,#0
done:
    pop {r4-r6}
    pop {r3}
    bx r3

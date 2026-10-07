/* Extra fixed-field format: up to three 9-bit existing compact glyph IDs in
 * the ORIGINAL four-byte name slot. Count is the initializer's actual arity.
 * r0 aligned slot, r1 owned output, r2 count 1..3, r3 output capacity.
 * Returns bytes incl NUL, or zero. Does not change persistent glyph encoding.
 */
    push {r4-r7,lr}
    cmp r2,#1
    blo fail
    cmp r2,#3
    bhi fail
    movs r4,#3
    tst r0,r4
    bne fail
    lsls r4,r2,#1
    adds r4,r4,r2
    adds r4,#1
    cmp r3,r4
    blo fail
    movs r7,r4
    ldr r4,[r0]
    movs r0,#9
    muls r0,r2
    movs r5,r4
    lsrs r5,r0
    cmp r5,#0
    bne fail
next_glyph:
    lsls r5,r4,#23
    lsrs r5,r5,#23
    lsrs r4,r4,#9
    movs r6,#1
divide31:
    cmp r5,#31
    blo write
    subs r5,#31
    adds r6,#1
    b divide31
write:
    movs r3,#127
    strb r3,[r1]
    strb r6,[r1,#1]
    adds r5,#1
    strb r5,[r1,#2]
    adds r1,#3
    subs r2,#1
    bne next_glyph
    movs r0,#0
    strb r0,[r1]
    movs r0,r7
    b done
fail:
    movs r0,#0
done:
    pop {r4-r7}
    pop {r1}
    bx r1

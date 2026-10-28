/* r0=caller-owned native copy, r1=exact bytes including NUL.
 * Source eligibility, keyboard exclusion and lifetime belong to the caller.
 * No ROM hook installs this component until those consumers are verified.
 */
    push {r4-r6,lr}
    movs r4,r0
    cmp r1,#0
    beq bad
    movs r3,#72
    lsls r3,r3,#2
    cmp r1,r3
    bhi bad
    adds r5,r0,r1
    bcs bad
    movs r2,r0
validate:
    cmp r2,r5
    bhs bad
    ldrb r3,[r2]
    adds r2,#1
    cmp r3,#0
    beq end_check
    cmp r3,#31
    beq bad
    cmp r3,#127
    bne validate
    adds r0,r2,#2
    bcs bad
    cmp r0,r5
    bhs bad
    ldrb r3,[r2]
    subs r3,#1
    cmp r3,#30
    bhi bad
    ldrb r3,[r2,#1]
    subs r3,#1
    cmp r3,#30
    bhi bad
    movs r2,r0
    b validate
end_check:
    cmp r2,r5
    bne bad
    movs r2,#0
mark:
    ldrb r3,[r4]
    cmp r3,#0
    beq good
    cmp r3,#127
    beq glyph
    cmp r3,#32
    bne next
    cmp r2,#0
    beq next
    cmp r2,#10
    beq next
    cmp r2,#32
    beq next
    ldrb r6,[r4,#1]
    cmp r6,#0
    beq next
    cmp r6,#10
    beq next
    cmp r6,#32
    beq next
    movs r6,#31
    strb r6,[r4]
next:
    movs r2,r3
    adds r4,#1
    b mark
glyph:
    movs r2,r3
    adds r4,#3
    b mark
bad:
    movs r0,#0
    b done
good:
    movs r0,#1
done:
    pop {r4-r6}
    pop {r3}
    bx r3

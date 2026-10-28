/* r0=owned buffer,r1=capacity,r2=nowrap. Return valid r0, marker count r1. */
    push {r4-r7,lr}
    movs r4,r0
    adds r5,r0,r1
    bcs bad
    movs r6,r2
    movs r7,#0
loop:
    cmp r4,r5
    bhs bad
    ldrb r0,[r4]
    adds r4,#1
    cmp r0,#0
    beq good
    cmp r0,#31
    beq marker
    cmp r0,#127
    beq glyph
    subs r0,#32
    cmp r0,#94
    bls loop
    cmp r6,#0
    bne bad
    adds r0,#32
    cmp r0,#10
    beq loop
    cmp r0,#16
    beq loop
    cmp r0,#17
    bne bad
    cmp r4,r5
    bhs bad
    ldrb r0,[r4]
    cmp r0,#0
    beq good
    b bad
marker:
    adds r7,#1
    b loop
glyph:
    adds r0,r4,#2
    bcs bad
    cmp r0,r5
    bhs bad
    ldrb r0,[r4]
    subs r0,#1
    cmp r0,#30
    bhi bad
    lsls r1,r0,#5
    subs r1,r1,r0
    ldrb r0,[r4,#1]
    subs r0,#1
    cmp r0,#30
    bhi bad
    adds r0,r0,r1
    lsrs r0,#9
    bne bad
    adds r4,#2
    b loop
good:
    movs r0,#1
    movs r1,r7
    b done
bad:
    movs r0,#0
    movs r1,#0
done:
    pop {r4-r7}
    pop {r3}
    bx r3

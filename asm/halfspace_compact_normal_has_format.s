/* Bounded prepared copy r0/bytes r1. Preserve r1; never inspect glyph params. */
    adds r2,r0,r1
    bcs yes
loop:
    cmp r0,r2
    bhs yes
    ldrb r3,[r0]
    adds r0,#1
    cmp r3,#0
    beq no
    cmp r3,#37
    beq yes
    cmp r3,#127
    bne loop
    adds r0,#2
    bcs yes
    b loop
no:
    movs r0,#0
    bx lr
yes:
    movs r0,#1
    bx lr

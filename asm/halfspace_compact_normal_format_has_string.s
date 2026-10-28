/* Prepared bounded template: 0=plain, 1=string argument, 2=other format.
 * Skip glyph parameters so byte 0x25 within a glyph is not a format. */
    movs r3,#0
loop:
    ldrb r2,[r0]
    adds r0,#1
    cmp r2,#0
    beq absent
    cmp r2,#127
    bne ascii
    adds r0,#2
    b loop
ascii:
    cmp r2,#37
    bne loop
    movs r3,#2
    ldrb r2,[r0]
    cmp r2,#115
    bne loop
    movs r0,#1
    bx lr
absent:
    movs r0,r3
    bx lr

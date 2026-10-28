/* Immutable registered labels are build-audited for singleton interior spaces
 * and bounded glyphIDs. EQ=valid; NE=native fallback; R2 profile preserved.
 */
next:
    ldrb r1,[r0]
    cmp r1,#127
    beq glyph
    cmp r1,#32
    beq space
    cmp r1,#0
    bx lr
glyph:
    adds r0,#2
space:
    adds r0,#1
    b next

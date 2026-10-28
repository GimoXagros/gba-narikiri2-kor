/* Exact immutable numeric-only formats need no lexical preparation.
 * Preserve all input registers and LR before either tail call. */
    ldr r3,first
    cmp r1,r3
    beq native
    adds r3,#4
    cmp r1,r3
    beq native
    adds r3,#4
    cmp r1,r3
    beq native
    ldr r3,costume
    cmp r1,r3
    beq native
    adds r3,#4
    cmp r1,r3
    beq native
    adds r3,#4
    cmp r1,r3
    beq native
    ldr r3,level
    cmp r1,r3
    beq native
    adds r3,#8
    cmp r1,r3
    beq native
    adds r3,#8
    cmp r1,r3
    beq native
    ldr r3,prepared
    bx r3
native:
    ldr r3,original
    bx r3
    .balign 4,0
first: .word 0x082c49a4
costume: .word 0x082c4c64
level: .word 0x082c3e40
prepared: .word NORMAL_FORMAT+1
original: .word NORMAL_NATIVE_FORMAT+1

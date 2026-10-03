/* ARM7TDMI Thumb-1 experimental bounded glyph-prefix decoder.
 * r0=input, r1=slot bytes, r2=output, r3=output capacity;
 * [sp]=book, [sp+4]=book bytes. Returns r0=native bytes incl NUL,
 * r1=encoded bytes consumed; r0=0 on malformed input/capacity failure.
 * EOS may precede untouched slot suffix; padding in its own byte must be zero.
 * Shared immutable tree must be validated at build time. Runtime checks all
 * traversed node indices, leaves and input/output extents. No game hook yet.
 */
strict_unit_decode:
    push {r4-r7, lr}
    sub sp, #20
    str r2, [sp]
    str r1, [sp, #16]
    ldr r4, [sp, #40]
    ldr r5, [sp, #44]
    cmp r5, #28
    blo unit_header_fail
    ldrh r6, [r4]
    cmp r6, #3
    blo unit_header_fail
    lsrs r7, r6, #15
    bne unit_header_fail
    lsls r7, r6, #3
    adds r7, #4
    cmp r7, r5
    bne unit_header_fail
    ldrh r7, [r4, #2]
    cmp r7, #0
    bne unit_header_fail
    str r6, [sp, #4]
    adds r4, #4
    movs r7, r4
    movs r5, #0
    b unit_next_bit
unit_header_fail:
    b unit_fail
unit_next_bit:
    cmp r5, #0
    bne unit_have_byte
    cmp r1, #0
    beq unit_walk_fail
    ldrb r6, [r0]
    adds r0, #1
    subs r1, #1
    lsls r6, r6, #24
    movs r5, #8
unit_have_byte:
    lsls r6, r6, #1
    bcs unit_right
    ldrh r7, [r7]
    b unit_child
unit_right:
    ldrh r7, [r7, #2]
unit_child:
    subs r5, #1
    str r0, [sp, #8]
    ldr r0, [sp, #4]
    cmp r7, r0
    bhs unit_walk_fail
    lsls r7, r7, #3
    adds r7, r4, r7
    ldrh r0, [r7]
    lsrs r0, r0, #15
    bne unit_leaf
    ldr r0, [sp, #8]
    b unit_next_bit
unit_walk_fail:
    b unit_fail
unit_leaf:
    ldrh r0, [r7]
    lsls r0, r0, #17
    lsrs r0, r0, #17
    cmp r0, #3
    bhi unit_fail
    cmp r3, r0
    bls unit_fail
    cmp r0, #0
    beq unit_eos
    str r1, [sp, #12]
    movs r1, r0
    adds r7, #4
unit_copy:
    ldrb r0, [r7]
    cmp r0, #0
    beq unit_fail
    strb r0, [r2]
    adds r7, #1
    adds r2, #1
    subs r3, #1
    subs r1, #1
    bne unit_copy
    ldr r0, [sp, #8]
    ldr r1, [sp, #12]
    movs r7, r4
    b unit_next_bit
unit_eos:
    cmp r6, #0
    bne unit_fail
    movs r0, #0
    strb r0, [r2]
    adds r2, #1
    ldr r0, [sp]
    subs r0, r2, r0
    ldr r2, [sp, #16]
    subs r1, r2, r1
    b unit_return
unit_fail:
    movs r0, #0
    movs r1, #0
unit_return:
    add sp, #20
    pop {r4-r7, pc}

/* ARM7TDMI Thumb-1 experimental bounded glyph-prefix decoder.
 * r0=input, r1=slot bytes, r2=output, r3=output capacity;
 * [sp]=book, [sp+4]=book bytes. Returns r0=native bytes incl NUL,
 * r1=encoded bytes consumed; r0=0 on malformed input/capacity failure.
 * EOS may precede untouched slot suffix; padding in its own byte must be zero.
 * [sp+8]=part count (1 or 4), [sp+12]=selection bitmask. For inline
 * alternatives use parts [prefix,left,right,suffix], masks 11 and 13.
 * Shared immutable tree must be validated at build time. Runtime checks all
 * traversed node indices, leaves and input/output extents. No game hook yet.
 * Book must be halfword aligned; input/output may be byte aligned. All spans
 * are nonempty, must not wrap, and output must not overlap input, dictionary,
 * or this frame/stack arguments. Caller proves readable/writable bus regions.
 * Only documented selections 1 (plain), 11/13 (bundle) are accepted.
 * Failure returns 0/0; output may be partial and must not be consumed.
 */
strict_unit_bundle_decode:
    push {r4-r7, lr}
    sub sp, #28
    str r2, [sp]
    str r0, [sp, #8]
    str r1, [sp, #16]
    ldr r4, [sp, #48]
    ldr r5, [sp, #52]
    /* Check spans before any input, book or output memory access. */
    cmp r1, #0
    beq unit_header_fail
    cmp r3, #0
    beq unit_header_fail
    movs r6, #1
    tst r4, r6
    bne unit_header_fail
    adds r6, r0, r1
    bcs unit_header_fail
    adds r7, r2, r3
    bcs unit_header_fail
    cmp r2, r6
    bhs unit_source_disjoint
    cmp r0, r7
    blo unit_header_fail
unit_source_disjoint:
    adds r6, r4, r5
    bcs unit_header_fail
    cmp r2, r6
    bhs unit_book_disjoint
    cmp r4, r7
    blo unit_header_fail
unit_book_disjoint:
    mov r6, sp
    cmp r7, r6
    bls unit_stack_disjoint
    adds r6, #64
    cmp r2, r6
    blo unit_header_fail
unit_stack_disjoint:
    ldr r6, [sp, #56]
    ldr r7, [sp, #60]
    cmp r6, #1
    bne unit_bundle_count
    cmp r7, #1
    bne unit_header_fail
    b unit_count_ok
unit_bundle_count:
    cmp r6, #4
    bne unit_header_fail
    cmp r7, #11
    beq unit_count_ok
    cmp r7, #13
    bne unit_header_fail
unit_count_ok:
    str r6, [sp, #20]
    str r7, [sp, #24]
    ldr r0, [sp, #8]
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
    cmp r0, #0
    beq unit_part_eos
    str r1, [sp, #12]
    ldr r1, [sp, #24]
    lsls r1, r1, #31
    beq unit_skip_leaf
    ldr r1, [sp, #12]
    cmp r3, r0
    bls unit_fail
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
unit_skip_leaf:
    movs r1, r0
    adds r7, #4
unit_skip_check:
    ldrb r0, [r7]
    cmp r0, #0
    beq unit_fail
    adds r7, #1
    subs r1, #1
    bne unit_skip_check
    ldr r0, [sp, #8]
    ldr r1, [sp, #12]
    movs r7, r4
    b unit_next_bit
unit_part_eos:
    ldr r0, [sp, #20]
    subs r0, #1
    str r0, [sp, #20]
    beq unit_final_eos
    ldr r0, [sp, #24]
    lsrs r0, #1
    str r0, [sp, #24]
    ldr r0, [sp, #8]
    movs r7, r4
    b unit_next_bit
unit_final_eos:
    cmp r3, #0
    beq unit_fail
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
    add sp, #28
    pop {r4-r7, pc}

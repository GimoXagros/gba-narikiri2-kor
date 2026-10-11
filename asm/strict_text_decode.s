/* ARM7TDMI Thumb-1, experimental bounded phrase decoder.
 * r0=stream, r1=exact available stream bytes, r2=output, r3=output capacity,
 * fifth AAPCS stack argument [sp]=1121-byte codebook. Returns bytes written
 * INCLUDING NUL, or zero for malformed/truncated/overlong input. Keeps
 * r4-r7 and SP. The caller owns both source extent and output RAM lifetime.
 * No game consumer is hooked to this routine yet.
 */
strict_text_decode:
    push {r4-r7, lr}
    sub sp, #4
    str r2, [sp]
    ldr r4, [sp, #24]
decode_next:
    cmp r1, #0
    beq decode_fail
    ldrb r5, [r0]
    adds r0, #1
    subs r1, #1
    cmp r5, #0
    beq decode_eos
    ldrb r6, [r4]
    cmp r5, r6
    beq decode_escape
    adds r6, r4, #1
    ldrb r6, [r6, r5]
    cmp r6, #255
    beq decode_literal
    cmp r6, #96
    bhs decode_fail
    lsls r7, r6, #3
    adds r7, r7, r6
    adds r6, r4, #1
    adds r6, #255
    adds r6, #1
    adds r6, r6, r7
    ldrb r7, [r6]
    cmp r7, #2
    blo decode_fail
    cmp r7, #8
    bhi decode_fail
    adds r6, #1
decode_phrase_byte:
    cmp r3, #1
    bls decode_fail
    ldrb r5, [r6]
    cmp r5, #0
    beq decode_fail
    strb r5, [r2]
    adds r6, #1
    adds r2, #1
    subs r3, #1
    subs r7, #1
    bne decode_phrase_byte
    b decode_next
decode_escape:
    cmp r1, #0
    beq decode_fail
    ldrb r5, [r0]
    adds r0, #1
    subs r1, #1
    cmp r5, #0
    beq decode_fail
decode_literal:
    cmp r3, #1
    bls decode_fail
    strb r5, [r2]
    adds r2, #1
    subs r3, #1
    b decode_next
decode_eos:
    cmp r1, #0
    bne decode_fail
    cmp r3, #0
    beq decode_fail
    movs r5, #0
    strb r5, [r2]
    adds r2, #1
    ldr r5, [sp]
    subs r2, r2, r5
    movs r0, r2
    b decode_return
decode_fail:
    movs r0, #0
decode_return:
    add sp, #4
    pop {r4-r7, pc}

/* Internal 9A99C contract: r4=160-byte buffer, r5=&length, r7=&logical count.
 * Preserve the original logical36 kinsoku clock and72 page boundary. Physical
 * LF placement uses half-cell widths and never adds another logical count.
 */
event_wrap:
    push {r4-r7,lr}
    sub sp,#8
    subs r0,#36
    cmp r0,#36
    bhs finished
    /* Substitution handlers append one byte per call. Never split a pair. */
    lsls r1,r0,#31
    bmi finished
    ldr r6,[r5]
    cmp r6,#2
    blo finished
    cmp r6,#158
    bhi finished
    adds r6,r6,r4
    str r6,[sp,#4]
    cmp r0,#0
    bne scan
    subs r0,r6,#1
    ldrb r1,[r0]
    cmp r1,#10
    beq finished
    subs r0,#1
    bl 0x0809a968
    cmp r0,#0
    bne scan
    movs r0,#38
    str r0,[r7]
scan:
    mov r0,r4
    movs r1,#0
scan_loop:
    ldrb r3,[r0]
    cmp r3,#10
    bne scan_token
    adds r0,#1
    mov r4,r0
    movs r1,#0
    b scan_check
scan_token:
    /* Mixed single-byte controls/kana use the native printer's pixel wrap.
     * Do not guess a pair boundary through an expanded variable decoration. */
    cmp r3,#128
    blo finished
    cmp r3,#159
    bls scan_pair
    cmp r3,#224
    blo finished
scan_pair:
    adds r1,#2
    cmp r3,#128
    bne scan_next
    ldrb r3,[r0,#1]
    cmp r3,#64
    bne scan_next
    subs r1,#1
scan_next:
    adds r0,#2
scan_check:
    cmp r0,r6
    blo scan_loop
scan_done:
    cmp r1,#36
    blo finished
    str r1,[sp]
    subs r6,#2
    mov r0,r6
    bl 0x0809a968
    cmp r0,#0
    beq insert_lf
    ldr r1,[sp]
    cmp r1,#36
    bls finished
closing_run:
    cmp r6,r4
    bls finished
    subs r6,#2
    mov r0,r6
    bl 0x0809a968
    cmp r0,#0
    bne closing_run
insert_lf:
    ldr r0,[sp,#4]
move_tail:
    cmp r0,r6
    bls moved
    subs r0,#1
    ldrb r1,[r0]
    strb r1,[r0,#1]
    b move_tail
moved:
    movs r0,#10
    strb r0,[r6]
    ldr r0,[r5]
    adds r0,#1
    str r0,[r5]
finished:
    add sp,#8
    pop {r4-r7,pc}

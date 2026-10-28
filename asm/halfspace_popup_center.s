/* Native25D08 entry from the unchanged banked popup adapter.
 * R4=object+4 text, R6=source, R3=0; stacked R4/R5/R6/LR are adapter-owned.
 * Empty/no8040 strings retain native12px rounding. With8040, center on the
 * existing6px grid; exact3px ties round left. Never increase slot overflow.
 */
popup_center:
    mov r5,r6
    movs r2,#0
popup_scan:
    ldrb r0,[r5]
    cmp r0,#0
    beq popup_measured
    adds r5,#1
    cmp r0,#31
    bls popup_scan
    cmp r0,#222
    beq popup_scan
    cmp r0,#223
    beq popup_scan
    adds r3,#1
    cmp r0,#128
    bne popup_legacy_lead
    ldrb r1,[r5]
    cmp r1,#64
    bne popup_scan
    adds r2,#1
    b popup_two
popup_legacy_lead:
    cmp r0,#129
    blo popup_scan
    cmp r0,#159
    bls popup_two
    cmp r0,#224
    blo popup_scan
    cmp r0,#234
    bhi popup_scan
popup_two:
    adds r5,#1
    b popup_scan
popup_measured:
    subs r5,r5,r6
    cmp r5,#31
    bhi popup_reject
    cmp r2,#0
    beq popup_native_padding
    lsls r0,r3,#1
    subs r0,r0,r2
    movs r1,#36
    subs r1,r1,r0
    bmi popup_legacy_fallback
    lsrs r1,r1,#1
    b popup_capacity
popup_legacy_fallback:
    adds r3,r3,r2
popup_native_padding:
    adds r0,r3,#1
    lsrs r0,r0,#1
    movs r1,#9
    subs r1,r1,r0
    bmi popup_copy
    lsls r1,r1,#1
popup_capacity:
    /* Each padding token needs2 bytes; retain the32-byte native text field. */
    adds r0,r1,#1
    lsrs r0,r0,#1
    lsls r0,r0,#1
    adds r0,r0,r5
    cmp r0,#31
    bls popup_padding
    b popup_copy
popup_padding:
    cmp r1,#0
    beq popup_copy
    movs r0,#129
    cmp r1,#1
    bne popup_pad_full
    movs r0,#128
popup_pad_full:
    strb r0,[r4]
    movs r0,#64
    strb r0,[r4,#1]
    adds r4,#2
    subs r1,#2
    bgt popup_padding
popup_copy:
    mov r0,r4
    mov r1,r6
    bl 0x080a6b90
popup_return:
    pop {r4-r6}
    pop {r0}
    bx r0
popup_reject:
    movs r0,#0
    strb r0,[r4]
    b popup_return

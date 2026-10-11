    push {r4, r5, r6, r7, lr}
    sub sp, #20
    adds r4, r0, #0
    ldr r0, font_base_global
    ldr r0, [r0]
    ldr r1, required_font_base
    cmp r0, r1
    beq guard_map
    b failure
guard_map:
    ldr r0, map_global
    ldr r0, [r0]
    ldr r1, required_map
    cmp r0, r1
    beq guard_tilebase
    b failure
guard_tilebase:
    ldr r0, tilebase_global
    ldr r0, [r0]
    cmp r0, #0
    beq guard_palette
    b failure
guard_palette:
    ldr r0, palette_global
    ldrb r0, [r0]
    cmp r0, #0
    beq begin
    cmp r0, #11
    beq begin
    b failure
begin:
    ldr r0, display_control
    ldrh r0, [r0]
    movs r1, #7
    ands r0, r1
    cmp r0, #1
    beq battle_profile
    ldr r0, first_tile
    movs r1, #72
    b save_profile
battle_profile:
    movs r0, #160
    lsls r0, r0, #1
    movs r1, #64
save_profile:
    str r0, [sp, #12]
    str r1, [sp, #16]
    adds r2, r1, #0
    ldr r1, [r4, #4]
    ldr r5, [sp, #12]
    lsls r5, r5, #5
    ldr r0, required_font_base
    adds r5, r5, r0
    movs r6, #0
match_group:
    ldr r7, [r5, #4]
    cmp r1, r7
    bne check_slot_1
    bl compare_rest
check_slot_1:
    ldr r7, [r5, #36]
    cmp r1, r7
    bne check_slot_2
    adds r5, #32
    adds r6, #1
    bl compare_rest
    subs r5, #32
    subs r6, #1
check_slot_2:
    ldr r7, [r5, #68]
    cmp r1, r7
    bne check_slot_3
    adds r5, #64
    adds r6, #2
    bl compare_rest
    subs r5, #64
    subs r6, #2
check_slot_3:
    ldr r7, [r5, #100]
    cmp r1, r7
    bne next_match_group
    adds r5, #96
    adds r6, #3
    bl compare_rest
    subs r5, #96
    subs r6, #3
next_match_group:
    adds r5, #128
    adds r6, #4
    cmp r6, r2
    blo match_group
    b no_match
compare_rest:
    ldr r3, [r4, #12]
    ldr r7, [r5, #12]
    cmp r3, r7
    bne compare_mismatch
    ldr r3, [r4, #8]
    ldr r7, [r5, #8]
    cmp r3, r7
    bne compare_mismatch
    ldr r3, [r4, #20]
    ldr r7, [r5, #20]
    cmp r3, r7
    bne compare_mismatch
    ldr r3, [r4]
    ldr r7, [r5]
    cmp r3, r7
    bne compare_mismatch
    ldr r3, [r4, #24]
    ldr r7, [r5, #24]
    cmp r3, r7
    bne compare_mismatch
    ldr r3, [r4, #28]
    ldr r7, [r5, #28]
    cmp r3, r7
    bne compare_mismatch
    ldr r3, [r4, #16]
    ldr r7, [r5, #16]
    cmp r3, r7
    bne compare_mismatch
    b success
compare_mismatch:
    bx lr
no_match:
    lsls r0, r2, #22
    mov r12, r0
    ldr r5, [sp, #12]
    lsls r5, r5, #22
    movs r0, #0
    str r0, [sp]
    str r0, [sp, #4]
    str r0, [sp, #8]
    ldr r0, shadow_map
    movs r1, #160
    lsls r1, r1, #2
    mov r2, sp
    bl mark_live
    ldr r0, display_control
    ldrh r0, [r0]
    movs r1, #1
    lsls r1, r1, #8
    tst r0, r1
    beq visible_marked
    ldr r0, required_map
    movs r1, #1
    lsls r1, r1, #10
    mov r2, sp
    bl mark_live
visible_marked:
    movs r6, #0
free_slot:
    lsrs r0, r6, #5
    lsls r0, r0, #2
    add r0, sp, r0
    ldr r1, [r0]
    movs r2, #31
    ands r2, r6
    movs r3, #1
    lsls r3, r2
    tst r1, r3
    beq copy_setup
    adds r6, #1
    ldr r0, [sp, #16]
    cmp r6, r0
    blo free_slot
    b failure
copy_setup:
    ldr r1, [sp, #12]
    lsls r1, r1, #5
    ldr r0, required_font_base
    adds r1, r1, r0
    lsls r0, r6, #5
    adds r1, r1, r0
    adds r0, r4, #0
    ldmia r0!, {r2, r3, r4, r5}
    stmia r1!, {r2, r3, r4, r5}
    ldmia r0!, {r2, r3, r4, r5}
    stmia r1!, {r2, r3, r4, r5}
success:
    ldr r0, [sp, #12]
    adds r0, r0, r6
    b done
failure:
    movs r0, #0
    mvns r0, r0
done:
    add sp, #20
    pop {r4, r5, r6, r7}
    pop {r1}
    bx r1
mark_live:
    ldmia r0!, {r2, r3, r6, r7}
    orrs r3, r2
    orrs r3, r6
    orrs r3, r7
    lsrs r6, r3, #16
    orrs r3, r6
    lsls r3, r3, #23
    bmi scan_eight
    b skip_eight
scan_eight:
    subs r0, #16
    mov r2, sp
    ldrh r3, [r0, #0]
    lsls r3, r3, #22
    subs r3, r3, r5
    cmp r3, r12
    bhs next_entry_0
    lsrs r3, r3, #22
    movs r6, #1
    movs r7, #31
    ands r7, r3
    lsls r6, r7
    lsrs r3, r3, #5
    lsls r3, r3, #2
    adds r3, r2, r3
    ldr r7, [r3]
    orrs r7, r6
    str r7, [r3]
next_entry_0:
    ldrh r3, [r0, #2]
    lsls r3, r3, #22
    subs r3, r3, r5
    cmp r3, r12
    bhs next_entry_1
    lsrs r3, r3, #22
    movs r6, #1
    movs r7, #31
    ands r7, r3
    lsls r6, r7
    lsrs r3, r3, #5
    lsls r3, r3, #2
    adds r3, r2, r3
    ldr r7, [r3]
    orrs r7, r6
    str r7, [r3]
next_entry_1:
    ldrh r3, [r0, #4]
    lsls r3, r3, #22
    subs r3, r3, r5
    cmp r3, r12
    bhs next_entry_2
    lsrs r3, r3, #22
    movs r6, #1
    movs r7, #31
    ands r7, r3
    lsls r6, r7
    lsrs r3, r3, #5
    lsls r3, r3, #2
    adds r3, r2, r3
    ldr r7, [r3]
    orrs r7, r6
    str r7, [r3]
next_entry_2:
    ldrh r3, [r0, #6]
    lsls r3, r3, #22
    subs r3, r3, r5
    cmp r3, r12
    bhs next_entry_3
    lsrs r3, r3, #22
    movs r6, #1
    movs r7, #31
    ands r7, r3
    lsls r6, r7
    lsrs r3, r3, #5
    lsls r3, r3, #2
    adds r3, r2, r3
    ldr r7, [r3]
    orrs r7, r6
    str r7, [r3]
next_entry_3:
    ldrh r3, [r0, #8]
    lsls r3, r3, #22
    subs r3, r3, r5
    cmp r3, r12
    bhs next_entry_4
    lsrs r3, r3, #22
    movs r6, #1
    movs r7, #31
    ands r7, r3
    lsls r6, r7
    lsrs r3, r3, #5
    lsls r3, r3, #2
    adds r3, r2, r3
    ldr r7, [r3]
    orrs r7, r6
    str r7, [r3]
next_entry_4:
    ldrh r3, [r0, #10]
    lsls r3, r3, #22
    subs r3, r3, r5
    cmp r3, r12
    bhs next_entry_5
    lsrs r3, r3, #22
    movs r6, #1
    movs r7, #31
    ands r7, r3
    lsls r6, r7
    lsrs r3, r3, #5
    lsls r3, r3, #2
    adds r3, r2, r3
    ldr r7, [r3]
    orrs r7, r6
    str r7, [r3]
next_entry_5:
    ldrh r3, [r0, #12]
    lsls r3, r3, #22
    subs r3, r3, r5
    cmp r3, r12
    bhs next_entry_6
    lsrs r3, r3, #22
    movs r6, #1
    movs r7, #31
    ands r7, r3
    lsls r6, r7
    lsrs r3, r3, #5
    lsls r3, r3, #2
    adds r3, r2, r3
    ldr r7, [r3]
    orrs r7, r6
    str r7, [r3]
next_entry_6:
    ldrh r3, [r0, #14]
    lsls r3, r3, #22
    subs r3, r3, r5
    cmp r3, r12
    bhs next_entry_7
    lsrs r3, r3, #22
    movs r6, #1
    movs r7, #31
    ands r7, r3
    lsls r6, r7
    lsrs r3, r3, #5
    lsls r3, r3, #2
    adds r3, r2, r3
    ldr r7, [r3]
    orrs r7, r6
    str r7, [r3]
next_entry_7:
    adds r0, #16
skip_eight:
    subs r1, #8
    beq finish_mark
    b mark_live
finish_mark:
    bx lr
    .balign 4, 0
font_base_global: .word 0x03000050
required_font_base: .word 0x0600c000
map_global: .word 0x0300004c
required_map: .word 0x0600f800
tilebase_global: .word 0x03000054
palette_global: .word 0x0300145a
shadow_map: .word 0x03000058
display_control: .word 0x03000010
first_tile: .word 0x178

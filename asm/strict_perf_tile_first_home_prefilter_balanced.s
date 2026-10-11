    push {r4, r5, r6, r7, lr}
    sub sp, #20
    adds r4, r0, #0
    ldr r0, map_global
    ldmia r0!, {r1, r2, r3}
    ldr r0, required_font_base
    subs r2, r2, r0
    orrs r2, r3
    bne failure
guard_map:
    ldr r0, required_map
    cmp r1, r0
    bne failure
guard_tilebase:
guard_palette:
    ldr r0, palette_global
    ldrb r0, [r0]
    cmp r0, #0
    beq begin
    cmp r0, #11
    beq begin
failure:
    movs r0, #0
    mvns r0, r0
    b done
begin:
    /* Reuse the validated palette value in R2 until the first get_home. */
    adds r2, r0, #0
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
    /* Four immutable glyph-ID homes, exact32 verification then full scan. */
    ldr r1, [r4, #12]
    bl get_home
    str r6, [sp]
    adds r0, r6, #1
    beq native_scan
    movs r2, #4
home_probe:
    ldr r5, [sp, #12]
    adds r5, r5, r6
    lsls r5, r5, #5
    ldr r0, required_font_base
    adds r5, r5, r0
    ldr r7, [r5, #12]
    cmp r1, r7
    bne next_home_probe
    bl compare_rest
next_home_probe:
    adds r6, #17
    movs r0, #63
    ands r6, r0
    subs r2, #1
    bne home_probe
native_scan:
    ldr r2, [sp, #16]
    ldr r5, [sp, #12]
    lsls r5, r5, #5
    ldr r0, required_font_base
    adds r5, r5, r0
match_group:
    ldr r7, [r5, #12]
    cmp r1, r7
    bne native_next_0
    bl compare_rest
native_next_0:
    ldr r7, [r5, #44]
    cmp r1, r7
    bne native_next_1
    adds r5, #32
    bl compare_rest
    subs r5, #32
native_next_1:
    ldr r7, [r5, #76]
    cmp r1, r7
    bne native_next_2
    adds r5, #64
    bl compare_rest
    subs r5, #64
native_next_2:
    ldr r7, [r5, #108]
    cmp r1, r7
    bne native_next_3
    adds r5, #96
    bl compare_rest
    subs r5, #96
native_next_3:
    adds r5, #128
    subs r2, #4
    bne match_group
no_match:
    /* Only first home gets a direct exact-reference proof. If it is pinned,
     * replay the complete original bitmap/four-home/native fallback policy. */
    ldr r6, [sp]
    adds r0, r6, #1
    beq build_bitmap
    ldr r5, [sp, #12]
    adds r5, r5, r6
    lsls r5, r5, #22
    bl first_home_pinned
    ldr r6, [sp]
    beq copy_setup
build_bitmap:
    ldr r2, [sp, #16]
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
    bl mark_live
    ldr r0, display_control
    ldrh r0, [r0]
    lsrs r0, r0, #9
    bcc visible_marked
    ldr r0, required_map
    movs r1, #1
    lsls r1, r1, #10
    bl mark_live
visible_marked:
    /* mark_live clobbers R2, so refresh palette before the second get_home. */
    ldr r2, palette_global
    ldrb r2, [r2]
    bl get_home
    adds r0, r6, #1
    beq native_free
    movs r7, #4
home_free:
    bl slot_is_live
    beq copy_setup
    adds r6, #17
    movs r0, #63
    ands r6, r0
    subs r7, #1
    bne home_free
native_free:
    movs r6, #0
free_slot:
    bl slot_is_live
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
    ldr r0, [sp, #12]
    adds r0, r0, r6
    b done
success:
    lsls r0, r5, #18
    lsrs r0, r0, #23
    b done
done:
    add sp, #20
    pop {r4, r5, r6, r7}
    pop {r1}
    bx r1
slot_is_live:
    lsrs r0, r6, #5
    lsls r0, r0, #2
    add r0, sp, r0
    ldr r1, [r0]
    movs r3, #1
    negs r2, r6
    rors r3, r2
    tst r1, r3
    bx lr
compare_rest:
    ldr r3, [r4, #4]
    ldr r7, [r5, #4]
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
mark_live:
    ldmia r0!, {r2, r3, r6, r7}
    orrs r3, r2
    orrs r3, r6
    orrs r3, r7
    lsrs r6, r3, #16
    orrs r3, r6
    lsls r3, r3, #23
    bpl finish_eight
    /* Every tile in either profile has bit6 or bit7. This second
     * necessary condition only skips groups lacking both bits; otherwise
     * each raw halfword still undergoes the original exact range test. */
    lsls r3, r3, #1
    lsrs r3, r3, #30
    beq finish_eight
scan_eight:
    subs r0, #16
    movs r2, #4
scan_one:
    ldrh r3, [r0]
    lsls r3, r3, #22
    subs r3, r3, r5
    cmp r3, r12
    bhs next_entry_0
    lsrs r3, r3, #22
    /* ROR(1,-index) equals 1<<(index&31) for every profile slot. */
    movs r6, #1
    negs r7, r3
    rors r6, r7
    lsrs r3, r3, #5
    lsls r3, r3, #2
    add r3, sp
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
    /* ROR(1,-index) equals 1<<(index&31) for every profile slot. */
    movs r6, #1
    negs r7, r3
    rors r6, r7
    lsrs r3, r3, #5
    lsls r3, r3, #2
    add r3, sp
    ldr r7, [r3]
    orrs r7, r6
    str r7, [r3]
next_entry_1:
    adds r0, #4
    subs r2, #1
    bne scan_one
finish_eight:
    subs r1, #8
    bne mark_live
finish_mark:
    bx lr
get_home:
    /* Caller supplies the current palette byte in R2; no mutable cache. */
    cmp r2, #0
    bne no_home
    ldr r0, compact_font_start
    subs r6, r4, r0
    lsrs r0, r6, #14
    bne no_home
    lsls r0, r6, #27
    bne no_home
    lsrs r6, r6, #5
    lsrs r0, r6, #6
    eors r6, r0
    movs r0, #63
    ands r6, r0
    bx lr
no_home:
    movs r6, #0
    mvns r6, r6
    bx lr
first_home_pinned:
    /* R12 preserves LR until first-home return; first_home_scan preserves R12.
     * The caller retains its original home in sp[0]. Both profiles have
     * tile-ID bit8 set, so its absence rejects a group exactly. */
    mov r12, lr
    ldr r0, shadow_map
    movs r1, #160
    lsls r1, r1, #2
    bl first_home_scan
    bne first_home_return
    ldr r0, display_control
    ldrh r0, [r0]
    movs r1, #1
    lsls r1, r1, #8
    ands r0, r1
    beq first_home_return
    ldr r0, required_map
    movs r1, #1
    lsls r1, r1, #10
    bl first_home_scan
first_home_return:
    bx r12
first_home_scan:
    ldmia r0!, {r2, r3, r6, r7}
    orrs r3, r2
    orrs r3, r6
    orrs r3, r7
    lsrs r6, r3, #16
    orrs r3, r6
    lsls r3, r3, #23
    bpl first_home_skip_eight
    subs r0, #16
    movs r2, #8
first_home_scan_one:
    ldrh r3, [r0]
    lsls r3, r3, #22
    cmp r3, r5
    beq first_home_found
    adds r0, #2
    subs r2, #1
    bne first_home_scan_one
first_home_skip_eight:
    subs r1, #8
    bne first_home_scan
    movs r0, #0
    bx lr
first_home_found:
    movs r0, #1
    bx lr


    .hword 0x46c0
    .hword 0x46c0
    .balign 4, 0
compact_font_start: .word 0x080c6254
font_base_global: .word 0x03000050
required_font_base: .word 0x0600c000
map_global: .word 0x0300004c
required_map: .word 0x0600f800
tilebase_global: .word 0x03000054
palette_global: .word 0x0300145a
shadow_map: .word 0x03000058
display_control: .word 0x03000010
first_tile: .word 0x178

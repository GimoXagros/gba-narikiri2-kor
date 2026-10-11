/* Thumb-1 SELECT_JOB menu preparation, for AN9J JP Rev0 0801C3B4.
 * The original 201 ROM pointer values at 083AE0E0 are read unchanged.
 * r0=083AE0E0, r1=201*8 descriptor bytes, r2=owned pointer table,
 * r3=owned native-byte arena; [sp]=pointer-table end, [sp+4]=byte-arena end,
 * [sp+8]=compact book, [sp+12]=book size.
 * Return r0=decoded pointer table (202 entries including null) and r1=2200
 * used bytes, or r0=r1=0. Both arenas must remain owned until 08004D98
 * returns; its menu object retains the pointer table while the menu runs.
 * The caller must provide one distinct arena per nested invocation and must
 * not pass the table onward on failure. The ABI makes no RAM placement claim.
 * Descriptors: u16 encoded length, u16 exact native length incl NUL,
 * u8 selection, u8 part count, u16 zero. Index is the variant context.
 * Keep the decoder within Thumb BL range and include its own stack contract.
 */
strict_runtime_select_job:
    push {r4-r7, lr}
    sub sp, #28
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r7, r3
    str r2, [sp]
    str r3, [sp, #4]
    ldr r0, [sp, #48]
    str r0, [sp, #8]
    ldr r0, [sp, #52]
    str r0, [sp, #12]
    ldr r0, [sp, #56]
    str r0, [sp, #16]
    ldr r0, [sp, #60]
    str r0, [sp, #20]
    movs r0, #201
    str r0, [sp, #24]
    /* An exact source-table address is required; a bare stream pointer
     * cannot discriminate the six SELECT_JOB aliases. */
    movs r0, #0x08
    lsls r0, r0, #24
    movs r1, #0x3a
    lsls r1, r1, #16
    orrs r0, r1
    movs r1, #0xe0
    lsls r1, r1, #8
    orrs r0, r1
    movs r1, #0xe0
    orrs r0, r1
    cmp r4, r0
    bne strict_job_fail
    /* The output array needs 201 pointers plus its null sentinel. */
    movs r0, #202
    lsls r0, r0, #2
    adds r0, r6, r0
    bcs strict_job_fail
    ldr r1, [sp, #8]
    cmp r0, r1
    bhi strict_job_fail
    /* Reject arena overlap before writing either region. */
    cmp r7, r0
    bhs strict_job_loop
    ldr r1, [sp, #12]
    cmp r6, r1
    blo strict_job_fail
strict_job_loop:
    ldr r0, [r4]
    cmp r0, #0
    beq strict_job_fail
    ldrh r0, [r5, #2]
    cmp r0, #0
    beq strict_job_fail
    adds r0, r7, r0
    bcs strict_job_fail
    ldr r1, [sp, #12]
    cmp r0, r1
    bhi strict_job_fail
    sub sp, #16
    ldr r0, [sp, #32]
    str r0, [sp]
    ldr r0, [sp, #36]
    str r0, [sp, #4]
    ldrb r0, [r5, #5]
    str r0, [sp, #8]
    ldrb r0, [r5, #4]
    str r0, [sp, #12]
    ldr r0, [r4]
    ldrh r1, [r5]
    mov r2, r7
    ldrh r3, [r5, #2]
    bl strict_unit_bundle_decode
    add sp, #16
    cmp r0, #0
    beq strict_job_fail
    ldrh r2, [r5, #2]
    cmp r0, r2
    bne strict_job_fail
    ldrh r2, [r5]
    cmp r1, r2
    bne strict_job_fail
    str r7, [r6]
    adds r7, r7, r0
    adds r4, #4
    adds r5, #8
    adds r6, #4
    ldr r0, [sp, #24]
    subs r0, #1
    str r0, [sp, #24]
    bne strict_job_loop
    ldr r0, [r4]
    cmp r0, #0
    bne strict_job_fail
    str r0, [r6]
    ldr r0, [sp]
    ldr r1, [sp, #4]
    subs r1, r7, r1
    b strict_job_return
strict_job_fail:
    ldr r2, [sp]
    movs r3, #0
    str r3, [r2]
    movs r0, #0
    movs r1, #0
strict_job_return:
    add sp, #28
    pop {r4-r7, pc}

/* Replacement for the single BL at 0801C3B4. It owns one 3008-byte
 * allocation over the synchronous 08004D98 menu loop and frees it only
 * after that function destroys the menu object at 08004E50.
 * The descriptor/book literal words below are link-time relocations. Their
 * sentinels MUST be replaced by the integration builder and verified there.
 * If allocation or decode fails, return the menu's -1 cancellation value.
 */
strict_runtime_select_job_menu:
    push {r4-r7, lr}
    sub sp, #16
    str r0, [sp]
    str r1, [sp, #4]
    str r2, [sp, #8]
    str r3, [sp, #12]
    movs r0, #0xbc
    lsls r0, r0, #4
    bl strict_job_heap_alloc
    mov r4, r0
    cmp r4, #0
    beq strict_job_menu_cancel
    mov r5, r4
    movs r0, #202
    lsls r0, r0, #2
    adds r5, r5, r0
    mov r6, r4
    movs r0, #0xbc
    lsls r0, r0, #4
    adds r6, r6, r0
    sub sp, #16
    str r5, [sp]
    str r6, [sp, #4]
    ldr r0, strict_job_compact_book_ptr
    str r0, [sp, #8]
    ldr r0, strict_job_compact_book_size
    str r0, [sp, #12]
    ldr r0, [sp, #28]
    ldr r1, strict_job_descriptor_ptr
    mov r2, r4
    mov r3, r5
    bl strict_runtime_select_job
    add sp, #16
    cmp r0, #0
    beq strict_job_menu_free_cancel
    ldr r0, [sp]
    ldr r1, [sp, #4]
    ldr r2, [sp, #8]
    mov r3, r4
    bl strict_job_original_menu
    mov r5, r0
    mov r0, r4
    bl strict_job_heap_free
    mov r0, r5
    b strict_job_menu_return
strict_job_menu_free_cancel:
    mov r0, r4
    bl strict_job_heap_free
strict_job_menu_cancel:
    movs r0, #1
    rsbs r0, r0, #0
strict_job_menu_return:
    add sp, #16
    pop {r4-r7, pc}

/* Local veneers keep ARMv4T Thumb calls legal regardless of code placement. */
strict_job_heap_alloc:
    ldr r3, strict_job_heap_alloc_ptr
    bx r3
strict_job_heap_free:
    ldr r3, strict_job_heap_free_ptr
    bx r3
strict_job_original_menu:
    push {r4}
    ldr r4, strict_job_original_menu_ptr
    mov ip, r4
    pop {r4}
    bx ip
    .align 2
strict_job_descriptor_ptr: .word 0xDE5C0001
strict_job_compact_book_ptr: .word 0xDE5C0002
strict_job_compact_book_size: .word 7388
strict_job_heap_alloc_ptr: .word 0x08003521
strict_job_heap_free_ptr: .word 0x080035DD
strict_job_original_menu_ptr: .word 0x08004D99

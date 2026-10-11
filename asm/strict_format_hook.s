/* Diagnostic adapter for the original 08002648 formatter.
 * r0=original output buffer, r1=template, r2=vararg word cursor.
 * Only an exact start in the immutable descriptor table is compressed.
 * Decode before substitution; use original heap ownership, free synchronously
 * after formatter has copied the template. No decoded pointer is retained.
 * This adapter does not establish earlier script consumers or all-game closure.
 */
strict_format_hook:
    push {r4-r7, lr}
    sub sp, #28
    str r3, [sp, #24]
    movs r4, r0
    movs r5, r1
    movs r6, r2
    ldr r7, format_descriptors
    ldr r0, format_descriptor_count
format_find:
    cmp r0, #0
    beq format_native
    ldr r1, [r7]
    cmp r1, SOURCE_REGISTER
    beq format_compressed
    adds r7, #12
    subs r0, #1
    b format_find
format_native:
    movs r0, r4
    movs r1, r5
    movs r2, r6
    ldr r3, [sp, #24]
    bl format_original
    b format_return
format_compressed:
    ldr r0, [r7, #8]
    ldr r3, format_allocate
    bl format_call_r3
    cmp r0, #0
    beq format_failure
    str r0, [sp, #16]
    movs r2, r0
    ldr r0, format_book
    str r0, [sp]
    ldr r0, format_book_bytes
    str r0, [sp, #4]
    movs r0, #1
    str r0, [sp, #8]
    str r0, [sp, #12]
    movs r0, SOURCE_REGISTER
    ldr r1, [r7, #4]
    ldr r3, [r7, #8]
    bl STRICT_DECODER_ADDRESS
    cmp r0, #0
    beq format_decode_failure
    RESTORE_DECODED_ARGS
    ldr r3, [sp, #24]
    bl format_original
    str r0, [sp, #20]
    ldr r0, [sp, #16]
    ldr r3, format_free
    bl format_call_r3
    ldr r0, [sp, #20]
format_return:
    add sp, #28
    pop {r4-r7}
    pop {r1}
    bx r1
format_decode_failure:
    ldr r0, [sp, #16]
    ldr r3, format_free
    bl format_call_r3
format_failure:
    /* Diagnostic fail stop is never counted as successful output. */
    b format_failure
format_original:
    ORIGINAL_PRELUDE
    ldr r3, format_continuation
    bx r3
format_call_r3:
    bx r3
    .balign 4, 0
format_descriptors: .word FORMAT_DESCRIPTORS
format_descriptor_count: .word FORMAT_DESCRIPTOR_COUNT
format_book: .word FORMAT_BOOK
format_book_bytes: .word FORMAT_BOOK_BYTES
format_allocate: .word 0x08003521
format_free: .word 0x080035DD
format_continuation: .word ORIGINAL_CONTINUATION

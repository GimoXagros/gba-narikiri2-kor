/* Diagnostic ARTE_158/159 context bridge for AN9J JP Rev0.
 * Exact accessor context (index, selector=0) becomes one of two opaque tags.
 * The original table words and physical stream start stay unchanged. Every
 * other accessor result is returned unchanged. A plain ambiguous stream
 * pointer at the formatter fails closed. No persistent RAM context is used.
 * Install only with proved near veneers and a bounded compact codebook.
 */
strict_runtime_arte_accessor:
    push {r4, r5, lr}
    mov r4, r0
    mov r5, r1
    bl strict_arte_original_accessor
    cmp r5, #0
    bne strict_arte_access_return
    cmp r4, #158
    beq strict_arte_access_158
    cmp r4, #159
    bne strict_arte_access_return
    ldr r1, strict_arte_source_ptr
    cmp r0, r1
    bne strict_arte_fail_stop
    ldr r0, strict_arte_tag_159
    b strict_arte_access_return
strict_arte_access_158:
    ldr r1, strict_arte_source_ptr
    cmp r0, r1
    bne strict_arte_fail_stop
    ldr r0, strict_arte_tag_158
strict_arte_access_return:
    pop {r4, r5}
    pop {r1} /* discard entry BL return */
    pop {r1} /* caller LR saved by patched push {lr} */
    bx r1
    .align 2
strict_arte_formatter_offset: .word 0xDE5C1000

/* Wrapper for 08002648. r0=output, r1=template, r2=arg cursor, r3=other.
 * A tagged template is decoded to its own 10-byte heap object. The original
 * formatter consumes it synchronously and the wrapper frees it on return.
 */
strict_runtime_arte_formatter:
    push {r4-r7, lr}
    sub sp, #28
    mov r4, r0
    mov r5, r1
    mov r6, r2
    str r3, [sp, #24]
    ldr r0, strict_arte_tag_158
    cmp r5, r0
    beq strict_arte_format_158
    ldr r0, strict_arte_tag_159
    cmp r5, r0
    beq strict_arte_format_159
    ldr r0, strict_arte_source_ptr
    cmp r5, r0
    beq strict_arte_fail_stop
strict_arte_format_native:
    mov r0, r4
    mov r1, r5
    mov r2, r6
    ldr r3, [sp, #24]
    bl strict_arte_original_formatter
    b strict_arte_format_return
strict_arte_format_158:
    movs r7, #11
    b strict_arte_format_decode
strict_arte_format_159:
    movs r7, #13
strict_arte_format_decode:
    movs r0, #10
    bl strict_arte_heap_alloc
    cmp r0, #0
    beq strict_arte_fail_stop
    str r0, [sp, #16]
    mov r2, r0
    ldr r0, strict_arte_book_ptr
    str r0, [sp]
    ldr r0, strict_arte_book_size
    str r0, [sp, #4]
    movs r0, #4
    str r0, [sp, #8]
    str r7, [sp, #12]
    ldr r0, strict_arte_source_ptr
    movs r1, #7
    movs r3, #10
    bl strict_unit_bundle_decode
    cmp r0, #10
    bne strict_arte_format_decode_fail
    cmp r1, #7
    bne strict_arte_format_decode_fail
    mov r0, r4
    ldr r1, [sp, #16]
    mov r2, r6
    ldr r3, [sp, #24]
    bl strict_arte_original_formatter
    str r0, [sp, #20]
    ldr r0, [sp, #16]
    bl strict_arte_heap_free
    ldr r0, [sp, #20]
strict_arte_format_return:
    add sp, #28
    pop {r4-r7}
    pop {r1} /* discard entry BL return */
    pop {r1} /* caller LR saved by patched push {lr} */
    bx r1
strict_arte_format_decode_fail:
    ldr r0, [sp, #16]
    bl strict_arte_heap_free
strict_arte_fail_stop:
    b strict_arte_fail_stop

/* Replayed original entry instructions. BX keeps the LR of the BL to this
 * trampoline; original epilogue returns to our wrapper, not its caller.
 */
strict_arte_original_accessor:
    mov r2, r0
    cmp r1, #0
    beq strict_arte_original_access_name
    ldr r3, strict_arte_access_full_continuation
    bx r3
strict_arte_original_access_name:
    ldr r3, strict_arte_access_name_continuation
    bx r3
strict_arte_original_formatter:
    push {r4-r7, lr}
    sub sp, #8
    mov r7, r0
    mov r4, r1
    ldr r3, strict_arte_format_continuation
    bx r3
strict_arte_heap_alloc:
    ldr r3, strict_arte_alloc_ptr
    bx r3
strict_arte_heap_free:
    ldr r3, strict_arte_free_ptr
    bx r3
    .align 2
strict_arte_source_ptr: .word 0x082BCFE0
strict_arte_tag_158: .word 0x0A2BCFE0
strict_arte_tag_159: .word 0x0C2BCFE0
strict_arte_book_ptr: .word 0xDE5C0004
strict_arte_book_size: .word 7388
strict_arte_access_full_continuation: .word 0x08008C5B
strict_arte_access_name_continuation: .word 0x08008C6D
strict_arte_format_continuation: .word 0x08002651
strict_arte_alloc_ptr: .word 0x08003521
strict_arte_free_ptr: .word 0x080035DD

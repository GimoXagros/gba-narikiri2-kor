/* r0: exact stream pointer or native input. Returns r0 native pointer,
 * r1 heap owner (zero for native), r2 decoded bytes including NUL (or zero).
 * Failure returns zero/zero/zero. Caller retains owner through its complete
 * synchronous operation and frees it once. No global transient pointer.
 */
    push {r4-r7,lr}
    sub sp,#24
    movs r4,r0
    movs r0,#1
    str r0,[sp,#20]
    ldr r0,arte_tag_left
    cmp r4,r0
    beq tag_left
    ldr r0,arte_tag_right
    cmp r4,r0
    beq tag_right
    lsrs r0,r4,#24
    cmp r0,#10
    beq failed
    cmp r0,#12
    beq failed
    cmp r0,#8
    bne native
    movs r0,r4
    ldr r1,full_bounds
    ldr r2,full_count
    bl lookup_call
    cmp r0,#0
    beq compact
    movs r7,r0
    ldr r5,full_book
    ldr r6,full_book_bytes
    ldr r0,full_capacity
    b allocate
tag_left:
    movs r0,#11
    b tag_ready
tag_right:
    movs r0,#13
tag_ready:
    str r0,[sp,#20]
    ldr r4,arte_source
compact:
    movs r0,r4
    ldr r1,compact_bounds
    ldr r2,compact_count
    bl lookup_call
    cmp r0,#0
    beq native
    movs r7,r0
    ldr r0,[sp,#20]
    cmp r0,#1
    bne compact_context_valid
    ldr r1,alias_starts
    movs r2,#7
alias_check:
    ldmia r1!,{r0}
    cmp r4,r0
    beq failed
    subs r2,#1
    bne alias_check
compact_context_valid:
    ldr r5,compact_book
    ldr r6,compact_book_bytes
    ldr r0,compact_capacity
allocate:
    str r0,[sp,#16]
    ldr r3,heap_alloc
    bl call_r3
    cmp r0,#0
    beq failed
    movs r2,r0
    str r5,[sp]
    str r6,[sp,#4]
    ldr r6,[sp,#20]
    str r6,[sp,#12]
    movs r0,#1
    cmp r6,#1
    beq have_parts
    movs r0,#4
have_parts:
    str r0,[sp,#8]
    movs r0,r4
    movs r1,r7
    ldr r3,[sp,#16]
    str r2,[sp,#16]
    ldr r4,unit_decoder
    bl call_r4
    cmp r0,#0
    beq decode_failed
    movs r2,r0
    ldr r0,[sp,#16]
    movs r1,r0
    b done
decode_failed:
    ldr r0,[sp,#16]
    ldr r3,heap_free
    bl call_r3
failed:
    movs r0,#0
    movs r1,#0
    movs r2,#0
    b done
native:
    movs r0,r4
    movs r1,#0
    movs r2,#0
done:
    add sp,#24
    pop {r4-r7}
    pop {r3}
    bx r3
lookup_call:
    ldr r3,bounds_lookup
call_r3:
    bx r3
call_r4:
    bx r4
    .balign 4,0
arte_tag_left: .word 0x0a2bcfe0
arte_tag_right: .word 0x0c2bcfe0
arte_source: .word 0x082bcfe0
alias_starts: .word ALIAS_STARTS
full_bounds: .word FULL_BOUNDS
full_count: .word FULL_COUNT
full_book: .word FULL_BOOK
full_book_bytes: .word FULL_BOOK_BYTES
full_capacity: .word FULL_CAPACITY
compact_bounds: .word COMPACT_BOUNDS
compact_count: .word COMPACT_COUNT
compact_book: .word COMPACT_BOOK
compact_book_bytes: .word COMPACT_BOOK_BYTES
compact_capacity: .word COMPACT_CAPACITY
heap_alloc: .word 0x08003521
heap_free: .word 0x080035dd
unit_decoder: .word UNIT_DECODER
bounds_lookup: .word BOUNDS_LOOKUP

/* Caller-buffer ABI: r0 input, r1 destination, r2 capacity.
 * Native returns r1=r2=0; decoded r0=r1=destination, r2=bytes.
 * Failure returns zero/zero/zero. The caller owns the original destination
 * through its complete synchronous operation. No global transient pointer.
 */
    push {r4-r7,lr}
    sub sp,#32
    movs r4,r0
    str r1,[sp,#24]
    str r2,[sp,#28]
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
    /* Complete compact table occupies these two pages; exact lookup decides. */
    lsrs r0,r4,#16
    ldr r1,compact_first_page
    subs r0,r0,r1
    cmp r0,#1
    bls compact
full:
    movs r0,r4
    ldr r1,full_bounds
    ldr r2,full_count
    bl lookup_call
    cmp r0,#0
    beq extra
    movs r7,r0
    adr r3,full_profile
    ldmia r3!,{r0,r5,r6}
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
    beq full
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
    /* Build proves complete seven-entry alias starts strictly increase. */
    blo compact_context_valid
    subs r2,#1
    bne alias_check
compact_context_valid:
    movs r0,#COMPACT_CAPACITY
    adr r3,compact_profile
    ldmia r3!,{r5,r6}
    b allocate
extra:
    movs r0,r4
    ldr r1,extra_bounds
    ldr r2,extra_count
    bl lookup_call
    cmp r0,#0
    beq native
    movs r7,r0
    adr r3,extra_profile
    ldmia r3!,{r0,r5,r6}
allocate:
    ldr r2,[sp,#28]
    cmp r2,r0
    bhs capacity_ready
    movs r0,r2
capacity_ready:
    str r0,[sp,#16]
    ldr r2,[sp,#24]
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
    add sp,#32
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
full_profile:
    .word FULL_CAPACITY, FULL_BOOK, FULL_BOOK_BYTES
compact_bounds: .word COMPACT_BOUNDS
compact_count: .word COMPACT_COUNT
compact_profile:
    .word COMPACT_BOOK, COMPACT_BOOK_BYTES
unit_decoder: .word UNIT_DECODER
bounds_lookup: .word BOUNDS_LOOKUP

extra_bounds: .word EXTRA_BOUNDS
extra_count: .word EXTRA_COUNT
extra_profile:
    .word EXTRA_CAPACITY, EXTRA_BOOK, EXTRA_BOOK_BYTES

compact_first_page: .word COMPACT_FIRST_PAGE

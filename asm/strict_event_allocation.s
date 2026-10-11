/* Called only at original 08098980 after the event wrapper has decoded input.
 * Original r5=source; [entry sp]=first full-name pointer; sl=second full-name.
 * Replaces only the result allocation size, preserving original substitution.
 * The 6-character persistent full-name fields have 13 bytes including NUL.
 * Decoded input has at most 283 bytes including NUL. No transient pointer is
 * stored globally. The original caller continues owning/freeing the result.
 */
    push {r4-r7,lr}
    movs r6,r5
    ldr r0,[sp,#20]
    bl name_length
    movs r4,r0
    mov r0,sl
    bl name_length
    movs r5,r0
    movs r7,#1
    ldr r1,input_bound
scan:
    cmp r1,#0
    beq failed
    ldrb r0,[r6]
    cmp r0,#0
    beq allocate
    cmp r0,#64
    bne literal
    cmp r1,#1
    bls failed
    ldrb r0,[r6,#1]
    cmp r0,#66
    beq first
    cmp r0,#71
    bne literal
    adds r7,r7,r5
    b token
first:
    adds r7,r7,r4
token:
    adds r6,#2
    subs r1,#2
    b scan
literal:
    adds r7,#1
    adds r6,#1
    subs r1,#1
    b scan
allocate:
    movs r0,r7
    ldr r3,alloc_ptr
    bl call_r3
    cmp r0,#0
    beq failed
    pop {r4-r7}
    pop {r3}
    bx r3
name_length:
    movs r2,#0
name_loop:
    cmp r2,#13
    bhs failed
    ldrb r3,[r0,r2]
    cmp r3,#0
    beq name_done
    adds r2,#1
    b name_loop
name_done:
    movs r0,r2
    bx lr
failed:
    ldr r3,stop_ptr
call_r3:
    bx r3
    .balign 4,0
input_bound: .word 283
alloc_ptr: .word 0x08003521
stop_ptr: .word FAIL_STOP

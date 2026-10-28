/* Native 1DBC ABI; all prepared data remains on this invocation's stack. */
    push {r4-r7,lr}
    sub sp,#320
    movs r4,r0
    movs r5,r1
    movs r6,r2
    movs r0,r5
    mov r1,sp
    movs r2,#64
    bl NORMAL_FORMAT_PREPARE
    cmp r0,#0
    beq fallback
    mov r0,sp
    bl NORMAL_FORMAT_HAS_STRING
    cmp r0,#0
    beq plain
    cmp r0,#1
    bne ready
    ldr r0,[r6,#4]
    add r1,sp,#64
    bl NORMAL_ARGUMENT
    cmp r0,#0
    beq fallback
    movs r7,r0
    b args
ready:
    ldr r7,[r6,#4]
args:
    str r7,[sp,#288]
    ldr r0,[r6,#8]
    str r0,[sp,#292]
    ldr r0,[r6,#12]
    str r0,[sp,#296]
    add r0,sp,#128
    mov r1,sp
    add r2,sp,#288
    bl 0x08002648
    add r7,sp,#128
    b finish_ready
plain:
    mov r7,sp
finish_ready:
    ldr r3,finish
    bx r3
fallback:
    movs r0,r4
    movs r1,r5
    movs r2,r6
    bl NORMAL_NATIVE_FORMAT
    ldr r3,leave
    bx r3
    .balign 4,0
finish: .word NORMAL_FORMAT_FINISH+1
leave: .word NORMAL_FORMAT_LEAVE+1

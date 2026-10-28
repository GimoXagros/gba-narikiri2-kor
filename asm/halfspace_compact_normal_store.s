    adds r1,r0,#1
    beq fatal
    movs r1,#4
    ldrsb r1,[r4,r1]
    lsls r1,#1
    movs r2,#5
    ldrsb r2,[r4,r2]
    lsls r2,#6
    adds r1,r1,r2
    ldr r2,shadow
    adds r1,r1,r2
    ldrb r2,[r4,#7]
    lsls r2,#12
    orrs r0,r2
    strh r0,[r1]
    ldrb r0,[r4,#4]
    adds r0,#1
    strb r0,[r4,#4]
    bx lr
fatal:
    ldr r3,stop
    bx r3
    .balign 4,0
shadow: .word 0x03000058
stop: .word DIAGNOSTIC_STOP

    push {lr}
loop:
    ldrb r0,[r5]
    cmp r0,#0
    beq finish
    cmp r0,#31
    beq space
    cmp r0,#32
    blo control
    cmp r6,#0
    beq aligned
    mov r0,r8
    ldr r0,[r0,#116]
    cmp r0,#0
    bne aligned
    ldrb r0,[r4,#4]
    adds r0,#1
    ldrb r1,[r4,#2]
    cmp r0,r1
    blo aligned
    bl NORMAL_FLUSH
    movs r6,#0
aligned:
    cmp r6,#0
    bne resolve
    bl NORMAL_WRAP
resolve:
    bl NORMAL_GLYPH
    bl NORMAL_EMIT
    ldrb r0,[r5]
    cmp r0,#127
    bne next
    adds r5,#2
next:
    adds r5,#1
    b loop
space:
    bl NORMAL_SPACE
    b next
control:
    bl NORMAL_CONTROL
    b next
finish:
    bl NORMAL_FLUSH
    pop {pc}

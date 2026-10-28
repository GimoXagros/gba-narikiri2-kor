/* r0=validated native copy,r1=x,r2=y. Native simple palette is14. */
    push {r4-r6,lr}
    sub sp,#8
    movs r4,r0
    movs r5,r1
    movs r6,r2
    ldr r0,geometry
    str r0,[sp]
    mov r0,sp
    strb r5,[r0,#4]
    strb r6,[r0,#5]
    movs r1,#0
    strb r1,[r0,#6]
    movs r1,#14
    strb r1,[r0,#7]
    bl NORMAL_RENDER_GATE
    cmp r0,#0
    beq done
    movs r2,r1
    mov r0,sp
    movs r1,r4
    movs r3,#1
    bl NORMAL_DRAW
done:
    add sp,#8
    pop {r4-r6}
    pop {r3}
    bx r3
    .balign 4,0
geometry: .word 0x14200000

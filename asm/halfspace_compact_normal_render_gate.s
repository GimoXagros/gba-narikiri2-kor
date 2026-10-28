/* Guard the profile before any newly composed ASCII tile requests cache space. */
    push {r4,lr}
    movs r4,r0
    ldrb r1,[r4,#6]
    cmp r1,#1
    bhi bad
    ldrb r1,[r4,#2]
    cmp r1,#32
    bhi bad
    ldrb r2,[r4]
    cmp r2,r1
    bhs bad
    ldrb r2,[r4,#4]
    cmp r2,r1
    bhs bad
    ldrb r1,[r4,#3]
    cmp r1,#20
    bhi bad
    ldrb r2,[r4,#1]
    cmp r2,r1
    bhs bad
    ldrb r2,[r4,#5]
    cmp r2,r1
    bhs bad
    ldr r0,map_globals
    ldmia r0!,{r1-r3}
    cmp r3,#0
    bne bad
    ldr r0,map_base
    cmp r0,r1
    bne bad
    ldr r0,font_base
    cmp r0,r2
    bne bad
    ldr r0,clear_mode
    ldrb r1,[r0]
    cmp r1,#0
    beq good
    cmp r1,#11
    bne bad
good:
    movs r0,#1
    b done
bad:
    movs r0,#0
done:
    pop {r4}
    pop {r3}
    bx r3
    .balign 4,0
map_globals: .word 0x0300004c
map_base: .word 0x0600f800
font_base: .word 0x0600c000
clear_mode: .word 0x0300145a

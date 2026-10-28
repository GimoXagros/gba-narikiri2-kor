/* Bounded temporary copy; callers reject partial copies before formatting. */
    push {r4,lr}
    movs r2,r1
    movs r3,#64
    lsrs r4,r0,#24
    cmp r4,#8
    beq loop
    cmp r4,#2
    beq ewram
    cmp r4,#3
    bne bad
    ldr r4,iwram_end
    b bound
ewram:
    ldr r4,ewram_end
bound:
    subs r4,r4,r0
    bls bad
    cmp r4,#64
    bhs loop
    movs r3,r4
loop:
    ldrb r4,[r0]
    adds r0,#1
    strb r4,[r1]
    adds r1,#1
    cmp r4,#0
    beq done
    subs r3,#1
    bne loop
bad:
    movs r0,#0
    b leave
done:
    movs r0,r2
leave:
    pop {r4}
    pop {r3}
    bx r3
    .balign 4,0
ewram_end: .word 0x02040000
iwram_end: .word 0x03008000

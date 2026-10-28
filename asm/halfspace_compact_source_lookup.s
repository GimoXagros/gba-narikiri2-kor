/* Exact SBS2 lookup, preserving original source through both directories. */
    push {r4,lr}
    movs r4,r0
    ldr r1,compact_bounds
    ldrh r2,[r1,#6]
    bl 0x080b9d3c
    cmp r0,#0
    bne done
    movs r0,r4
    ldr r1,extra_bounds
    ldrh r2,[r1,#6]
    bl 0x080b9d3c
done:
    pop {r4}
    pop {r3}
    bx r3
    .balign 4,0
compact_bounds: .word 0x080c41dc
extra_bounds: .word 0x080c3f64

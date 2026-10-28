/* Invalidate only when native wrap changed XY; all other changes are our
 * own stores, whose returned cache slots have already been added to pins. */
batch_wrap:
    push {r4-r6,lr}
    adds r4,r0,#0
    ldrh r5,[r4,#4]
    bl 0x08001a80
    ldrh r0,[r4,#4]
    cmp r0,r5
    beq done
    bl BATCH_INIT
done:
    pop {r4-r6,pc}

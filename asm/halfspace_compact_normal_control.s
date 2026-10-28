/* A prompt is admitted only at NUL; flush before the native wait routine. */
    push {r5,lr}
    cmp r0,#17
    bne other
    bl NORMAL_PROMPT
    b done
other:
    movs r5,r0
    cmp r5,#10
    beq linefeed
    /* Clear replaces the whole field; a discarded half tile needs no slot. */
    movs r6,#0
    adds r0,r4,#0
    bl 0x08001858
    bl BATCH_INIT
    b done
linefeed:
    bl NORMAL_FLUSH
    movs r6,#0
    ldrb r1,[r4,#2]
    strb r1,[r4,#4]
    bl NORMAL_WRAP
done:
    pop {r5,pc}

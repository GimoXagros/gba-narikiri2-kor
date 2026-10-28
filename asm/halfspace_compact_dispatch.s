/* Caller-register provenance is checked before the original formatter.
 * JOB records retainR4; ITEM retainsR6 ID; ARTE retainsR4 ID.
 * Callback geometry/prefix/reset bytes are build-guarded; MONSTER gate isC.
 */
    push {r4-r7,lr}
    adds r5,r0,#0
    movs r6,#0
    ldr r0,varargs_return
    cmp lr,r0
    bne format
    ldr r3,[sp,#32]
    ldr r0,job_left
    cmp r3,r0
    beq job
    ldr r0,job_right
    cmp r3,r0
    beq job
    ldr r0,item_return
    cmp r3,r0
    beq item
    ldr r0,arte_return
    cmp r3,r0
    bne mon_check
    ldr r4,[sp]
    cmp r4,#232
    bhs format
    ldr r3,artes
    b index20
item:
    ldr r4,[sp,#8]
    cmp r4,#157
    bhs format
    ldr r3,items
index20:
    lsls r0,r4,#2
    adds r0,r0,r4
    lsls r0,r0,#2
    ldr r4,[r3,r0]
    b compare_source
job:
    ldr r4,[sp]
    lsrs r0,r4,#18
    cmp r0,#128
    bne format
    ldrb r4,[r4]
    cmp r4,#201
    bhs format
    lsls r4,r4,#6
    ldr r0,jobs
    ldr r4,[r0,r4]
compare_source:
    /* ROR25 accepts only exact08/0A/0C ROM identity; R1 alias/selector stays. */
    eors r4,r1
    movs r0,#25
    rors r4,r0
    cmp r4,#2
    bhi format
matched:
    ldrb r0,[r5,#6]
    cmp r0,#1
    bne format
    movs r6,#1
    b format
mon_check:
    bl MON_GATE
format:
    adds r2,#4
    ldr r4,buffer
    adds r0,r4,#0
    subs r0,#6
    ldrb r7,[r0]
    adds r0,r4,#0
    bl 0x08002648
    bl FINISH_DISPATCH
    .balign 4,0
varargs_return: .word 0x080cab55
job_left: .word 0x0800fed5
job_right: .word 0x0800f4c9
item_return: .word 0x080117a5
arte_return: .word 0x080140f5
jobs: .word 0x082b5810
items: .word 0x082b2cac
artes: .word 0x08374a38
buffer: .word 0x03001460

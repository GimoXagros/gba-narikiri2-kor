/* Stateless native numeric gap guard. All halfword pairs are build-derived
 * from the complete source numeric-literal population in the compact hull.
 * Only the matching physical page is admitted; no registered start is inside
 * any gap. Original r0/r1/r2 and r4-r11 survive fallback. No text is read.
 * The fallback replays the original first eight bytes at owned+0 before +8.
 */
    /* All 02/03-bank inputs are native under the original owned ABI. */
    lsrs r3,r0,#25
    cmp r3,#1
    bne inspect_rom
    movs r1,#0
    movs r2,#0
    bx lr
inspect_rom:
    push {r0-r2,r4-r7}
    ldr r1,source_page
    subs r4,r0,r1
    lsrs r3,r4,#16
    bne miss
    movs r5,#0
    movs r6,#GAP_COUNT
    ldr r7,gap_table
search:
    cmp r5,r6
    bhs miss
    subs r0,r6,r5
    lsrs r0,r0,#1
    adds r0,r0,r5
    lsls r1,r0,#2
    adds r1,r1,r7
    ldrh r2,[r1]
    cmp r4,r2
    blo lower
    ldrh r3,[r1,#2]
    cmp r4,r3
    blo native
    adds r5,r0,#1
    b search
lower:
    movs r6,r0
    b search
native:
    pop {r0-r2,r4-r7}
    movs r1,#0
    movs r2,#0
    bx lr
miss:
    pop {r0-r2,r4-r7}
fallback:
    push {r4-r7,lr}
    sub sp,#32
    movs r4,r0
    str r1,[sp,#24]
    ldr r3,resume
    bx r3
    .balign 4,0
source_page: .word SOURCE_BASE
gap_table: .word GAP_TABLE
resume: .word 0x080B9C09

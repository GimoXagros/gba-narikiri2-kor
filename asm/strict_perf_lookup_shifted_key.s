/* SBS2 metadata. r0 original start, r1 immutable word-aligned blob, r2 entries.
 * Header: magic, u16 pages, u16 entries, u32 entry-array offset.
 * Directory: u32 32KiB page base, u16 count, u16 first entry index.
 * Three-byte entry: low15 start in page, high9 exact original slot capacity.
 * No scanning text, inferred padding, or changed stream bits.
 */
    push {r4-r7,lr}
    sub sp,#8
    movs r7,r0
    lsrs r0,r0,#23
    cmp r0,#16
    bne absent
    movs r0,#3
    tst r0,r1
    bne absent
    ldr r0,[r1]
    ldr r3,magic
    cmp r0,r3
    bne absent
    ldrh r0,[r1,#6]
    cmp r0,r2
    bne absent
    ldrh r6,[r1,#4]
    ldr r0,[r1,#8]
    adds r0,r0,r1
    str r0,[sp,#4]
    adds r4,r1,#0
    adds r4,#12
    lsrs r0,r7,#15
    lsls r0,r0,#15
    str r0,[sp]
    lsls r7,r7,#17
    movs r5,#0
page_search:
    cmp r5,r6
    bhs absent
    subs r0,r6,r5
    lsrs r0,r0,#1
    adds r0,r0,r5
    lsls r1,r0,#3
    adds r1,r1,r4
    ldr r2,[r1]
    ldr r3,[sp]
    cmp r2,r3
    beq page_found
    blo page_higher
    movs r6,r0
    b page_search
page_higher:
    adds r5,r0,#1
    b page_search
page_found:
    ldrh r6,[r1,#4]
    ldrh r0,[r1,#6]
    lsls r1,r0,#1
    adds r0,r0,r1
    ldr r4,[sp,#4]
    adds r4,r4,r0
    movs r5,#0
entry_search:
    cmp r5,r6
    bhs absent
    subs r0,r6,r5
    lsrs r0,r0,#1
    adds r0,r0,r5
    lsls r1,r0,#1
    adds r1,r1,r0
    adds r2,r4,r1
    ldrb r3,[r2]
    ldrb r1,[r2,#1]
    lsls r1,r1,#8
    orrs r3,r1
    lsls r1,r3,#17
    cmp r1,r7
    beq found
    blo entry_higher
    movs r6,r0
    b entry_search
entry_higher:
    adds r5,r0,#1
    b entry_search
found:
    lsrs r0,r3,#15
    ldrb r1,[r2,#2]
    lsls r1,r1,#1
    orrs r0,r1
    b finish
absent:
    movs r0,#0
finish:
    add sp,#8
    pop {r4-r7}
    pop {r1}
    bx r1
    .balign 4,0
magic: .word 0x32534253

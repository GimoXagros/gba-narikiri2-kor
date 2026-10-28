/* Same34byte get_home owner. Original ROM glyph homes/guards stay exact.
 * RAM/solid tiles receive a content hint; every hit still compares32bytes,
 * and every replacement still proves both shadow/display maps unpinned.
 * Existing font literal is at080C5E28, PC-relative from080C5DB0.
 */
    cmp r2,#0
    bne pixel_home
    ldr r0,[pc,#0x74]
    subs r6,r4,r0
    lsrs r0,r6,#14
    bne pixel_home
    lsls r0,r6,#27
    bne pixel_home
    lsrs r0,r6,#6
    eors r6,r0
    lsls r6,r6,#21
    lsrs r6,r6,#26
    bx lr
pixel_home:
    lsrs r6,r1,#5
    eors r6,r1
    lsrs r6,r6,#26
    bx lr

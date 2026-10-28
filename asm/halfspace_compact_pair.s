/* r0=pending tile, r1=next full 8px glyph, r2=completed tile, r3=clear
 * halfword (0000 or BBBB). Pending holds the previous glyph's right 4px.
 * All three buffers are distinct, halfword aligned and exactly 32 bytes.
 * Only completed tiles may enter the live-aware cache; pending stays in RAM.
 */
    push {r4-r6,lr}
    movs r6,#8
row:
    ldrh r4,[r0]
    ldrh r5,[r1]
    strh r4,[r2]
    strh r5,[r2,#2]
    ldrh r4,[r1,#2]
    strh r4,[r0]
    strh r3,[r0,#2]
    adds r0,#4
    adds r1,#4
    adds r2,#4
    subs r6,#1
    bne row
    pop {r4-r6,pc}

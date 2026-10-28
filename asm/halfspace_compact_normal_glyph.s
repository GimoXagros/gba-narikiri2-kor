/* r0=pixels, r1=native ASCII tile or FFFFFFFF for a private glyph. */
    ldrb r0,[r5]
    cmp r0,#127
    beq hangul
    subs r0,#16
    ldr r1,tile_offset
    ldr r1,[r1]
    adds r1,r0,r1
    lsls r0,r1,#5
    ldr r2,vram_base
    ldr r2,[r2]
    adds r0,r0,r2
    bx lr
hangul:
    ldrb r0,[r5,#1]
    subs r0,#1
    lsls r1,r0,#5
    subs r1,r1,r0
    ldrb r0,[r5,#2]
    subs r0,#1
    adds r0,r0,r1
    lsls r0,#5
    ldr r1,font
    adds r0,r0,r1
    cmp r7,#0
    beq done
    mov r2,r8
    adds r2,#52
    movs r1,#8
copy:
    ldmia r0!,{r3}
    orrs r3,r7
    stmia r2!,{r3}
    subs r1,#1
    bne copy
    mov r0,r8
    adds r0,#52
done:
    movs r1,#0
    mvns r1,r1
    bx lr
    .balign 4,0
tile_offset: .word 0x03000054
vram_base: .word 0x03000050
font: .word COMPACT_FONT

/* Reserved space is normalized before any native font-table read. */
sprite_font:
    movs r2,#192
    negs r2,r2
    cmp r0,r2
    bne sprite_font_native
    movs r0,#0
sprite_font_native:
    ldr r3,sprite_native_font
    bx r3
    .balign 4,0
sprite_native_font: .word 0x080b9491

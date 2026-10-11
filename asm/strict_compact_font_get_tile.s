/* Same input/output contract as banked_get_tile; local tile lives through cache.
 * The existing cache copies/reuses the tile before returning a tile number.
 */
    push {r1-r7,lr}
    sub sp,#32
    ldr r3, decoder
    bl call_r3
    adds r1,r0,#1
    beq done
    mov r1,sp
    movs r2,#0
    ldr r3,palette_mode
    ldrb r3,[r3]
    cmp r3,#11
    bne unpack
    movs r2,#1
unpack:
    ldr r3,unpacker
    bl call_r3
    cmp r0,#0
    beq invalid
    ldr r3,cache
    bl call_r3
    b done
invalid:
    mvns r0,r0
done:
    add sp,#32
    pop {r1-r7}
    pop {r3}
    bx r3
call_r3:
    bx r3
    .balign 4,0
decoder: .word BANKED_DECODER
unpacker: .word FONT_UNPACKER
cache: .word TILE_CACHE
palette_mode: .word 0x0300145a

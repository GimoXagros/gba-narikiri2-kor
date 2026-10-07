push {r0-r7,lr}
ldr r4, display
ldrh r5, [r4]
ldr r6, ime
ldrh r7, [r6]
movs r0, #0
strh r0, [r6]
movs r0, #128
strh r0, [r4]
push {r5,r7}
ldr r0, packed_pixels
ldr r1, scratch
swi #0x12
ldr r4, scratch
ldr r1, vram
ldr r3, lut
ldr r2, packed_halfwords
expand:
ldrh r0, [r4]
adds r4, #2
lsrs r5, r0, #4
movs r6, #15
ands r5, r6
bl emit_nibble
movs r5, #15
ands r5, r0
bl emit_nibble
lsrs r5, r0, #12
bl emit_nibble
lsrs r5, r0, #8
movs r6, #15
ands r5, r6
bl emit_nibble
subs r2, #1
bne expand
pop {r5,r7}
ldr r4, display
ldr r6, ime
ldr r0, bitmap_mode
strh r0, [r4]
ldr r0, keys
ldr r2, key_mask
released:
ldrh r1, [r0]
ands r1, r2
cmp r1, r2
bne released
pressed:
ldrh r1, [r0]
ands r1, r2
cmp r1, r2
beq pressed
released_again:
ldrh r1, [r0]
ands r1, r2
cmp r1, r2
bne released_again
movs r0, #128
strh r0, [r4]
ldr r0, vram
ldr r1, vram_words
movs r2, #0
clear:
str r2, [r0]
adds r0, #4
subs r1, #1
bne clear
strh r5, [r4]
strh r7, [r6]
pop {r0-r7}
pop {r3}
mov lr, r3
ldr r3, original_main
bx r3
emit_nibble:
lsls r5, r5, #3
adds r5, r5, r3
ldr r6, [r5]
ldr r7, [r5, #4]
str r6, [r1]
str r7, [r1, #4]
adds r1, #8
bx lr
.balign 4
display: .word 0x04000000
ime: .word 0x04000208
packed_pixels: .word 0x08C91000
scratch: .word 0x06014000
vram: .word 0x06000000
lut: .word pixel_lut
packed_halfwords: .word 2400
bitmap_mode: .word 0x0403
keys: .word 0x04000130
key_mask: .word 0x03FF
vram_words: .word 24576
original_main: .word 0x08007401
pixel_lut:
    .word 0x00000000, 0x00000000
    .word 0x00000000, 0x7FFF0000
    .word 0x00000000, 0x00007FFF
    .word 0x00000000, 0x7FFF7FFF
    .word 0x7FFF0000, 0x00000000
    .word 0x7FFF0000, 0x7FFF0000
    .word 0x7FFF0000, 0x00007FFF
    .word 0x7FFF0000, 0x7FFF7FFF
    .word 0x00007FFF, 0x00000000
    .word 0x00007FFF, 0x7FFF0000
    .word 0x00007FFF, 0x00007FFF
    .word 0x00007FFF, 0x7FFF7FFF
    .word 0x7FFF7FFF, 0x00000000
    .word 0x7FFF7FFF, 0x7FFF0000
    .word 0x7FFF7FFF, 0x00007FFF
    .word 0x7FFF7FFF, 0x7FFF7FFF

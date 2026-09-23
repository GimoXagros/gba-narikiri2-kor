push {r0-r7,lr}
ldr r4, display
ldrh r5, [r4]
ldr r6, ime
ldrh r7, [r6]
movs r0, #0
strh r0, [r6]
movs r0, #128
strh r0, [r4]
ldr r0, pixels
ldr r1, vram
ldr r2, pixel_count
copy:
ldrh r3, [r0]
strh r3, [r1]
adds r0, #2
adds r1, #2
subs r2, #1
bne copy
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
.balign 4
display: .word 0x04000000
ime: .word 0x04000208
pixels: .word 0x08C91000
vram: .word 0x06000000
pixel_count: .word 38400
bitmap_mode: .word 0x0403
keys: .word 0x04000130
key_mask: .word 0x03FF
vram_words: .word 24576
original_main: .word 0x08007401

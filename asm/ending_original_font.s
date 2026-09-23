push {r4, lr}
ldr r0, font_stream
ldr r1, font_target
ldr r1, [r1]
ldr r3, decompress_vram
bl call_r3
pop {r4}
pop {r0}
mov lr, r0
push {lr}
movs r0, #3
movs r1, #30
movs r2, #0
ldr r3, original_tail
bx r3
call_r3:
bx r3
.balign 4
font_stream:
.word 0x08C86000
font_target:
.word 0x03000050
decompress_vram:
.word 0x080033AD
original_tail:
.word 0x080A59D5

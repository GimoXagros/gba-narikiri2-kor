/* Dedicated250E0 zeroes128B first. Preserve native13px matte height. */
sprite_postprocess:
    mov r1,r8
    ldrb r2,[r1]
    cmp r2,#128
    bne sprite_native_post
    ldrb r2,[r1,#1]
    cmp r2,#64
    bne sprite_native_post
    ldr r1,sprite_space_fill
    movs r2,#13
sprite_space_row:
    stm r0!,{r1}
    subs r2,#1
    cmp r2,#5
    bne sprite_space_no_jump
    adds r0,#32
sprite_space_no_jump:
    cmp r2,#0
    bne sprite_space_row
    bx lr
sprite_native_post:
sprite_old_post_load:
    ldr r3,[pc,#SHARED_POST_OFFSET]
    bx r3
    .balign 4,0
sprite_space_fill: .word 0x00bbbbbb




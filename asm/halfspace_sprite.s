/* Width is the explicit text-object immutable descriptor identity, never affine byte17.
 * The alias preserves all12 native frames and their nested descriptors.
 * Generic allocation, matrix index, priorities and saved identifiers stay native.
 */
sprite_created:
    movs r1,#2
    strb r1,[r0,#22]
    mov r2,r8
    ldrb r3,[r2]
    cmp r3,#128
    bne sprite_created_done
    ldrb r3,[r2,#1]
    cmp r3,#64
    bne sprite_created_done
    ldr r2,sprite_half_descriptor
    str r2,[r0,#4]
sprite_created_done:
    bx lr

sprite_advance:
    ldr r0,[r0,#4]
    mov r12,r2
    ldr r2,sprite_half_descriptor
    cmp r0,r2
    mov r2,r12
    beq sprite_half
    adds r1,#12
    b sprite_advanced
sprite_half:
    adds r1,#6
sprite_advanced:
    lsls r1,r1,#16
    lsrs r1,r1,#16
    bx lr

    .balign 4,0
sprite_half_descriptor: .word SPRITE_DESCRIPTOR

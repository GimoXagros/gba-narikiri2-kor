/* Default IRQ profile has only VBlank sound/serial and fatal GamePak IRQ.
 * SoundInit's final magic proves the frozen FIFO destination setup ran.
 * DMA destination registers are write-only; never read them as a guard.
 */
batch_init:
    push {r4,r5,lr}
    mov r4,r8
    movs r0,#0
    mvns r0,r0
    str r0,[r4,#12]
    ldr r0,irq_globals
    ldr r1,[r0]
    ldr r2,irq_dispatch
    cmp r1,r2
    bne done
    subs r0,#12
    ldr r0,[r0]
    lsrs r1,r0,#18
    cmp r1,#128
    bne done
    ldr r1,[r0]
    ldr r2,sound_magic
    subs r1,r1,r2
    cmp r1,#1
    bhi done
    ldr r0,irq_table
    ldr r1,[r0]
    ldr r2,vblank_handler
    cmp r1,r2
    bne done
    ldr r0,ie
    ldrh r1,[r0]
    ldr r2,default_ie
    cmp r1,r2
    bne done
    ldr r0,dma_base
    ldrh r1,[r0,#10]
    lsls r1,#16
    bmi done
    ldrh r1,[r0,#46]
    lsls r1,#16
    bmi done
    movs r2,#0xb6
    lsls r2,#24
    ldrh r1,[r0,#22]
    lsls r1,#16
    bpl second
    cmp r1,r2
    bne done
second:
    ldrh r1,[r0,#34]
    lsls r1,#16
    bpl enabled
    cmp r1,r2
    bne done
enabled:
    movs r0,#0
    str r0,[r4,#12]
done:
    pop {r4,r5,pc}
    .balign 4,0
irq_globals: .word 0x03007ffc
irq_dispatch: .word 0x03002b40
irq_table: .word 0x03002b04
vblank_handler: .word 0x080004b1
ie: .word 0x04000200
default_ie: .word 0x2001
dma_base: .word 0x040000b0
sound_magic: .word 0x68736d53

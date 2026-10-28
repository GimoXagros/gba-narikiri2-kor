/* C-installed decompressor-unused40byte tail only. Exact native MONSTER
 * callbacks retain the ROMentry in savedR4; they already loaded[source]R1.
 * Both prove fixed6row/noappend geometry. Unknown calls never dereferenceR4.
 */
    ldr r0,left_return
    cmp r3,r0
    beq source
    ldr r0,right_return
    cmp r3,r0
    bne done
source:
    /* Reject RAM/SAV sources even with forged known-caller registers. */
    lsrs r0,r1,#26
    cmp r0,#2
    bne done
    ldr r4,[sp]
    ldr r4,[r4]
    cmp r4,r1
    bne done
    movs r6,#1
done:
    bx lr
call_r3:
    bx r3
    .balign 4,0
left_return: .word 0x08019155
right_return: .word 0x0800f54b

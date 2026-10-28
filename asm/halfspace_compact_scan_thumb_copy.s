/* Invocation-local exact native Thumb scanner, with bitmap base in r4.
 * Copy98B+2B padding; preserve original bitmap above the120B scratch frame. */
    push {r0-r2,r4,lr}
    sub sp,#100
    mov r4,sp
    ldr r0,source
    movs r2,#25
copy:
    ldmia r0!,{r3}
    stmia r4!,{r3}
    subs r2,#1
    bne copy
    add r3,sp,#100
    ldmia r3!,{r0-r2}
    add r4,sp,#120
    mov r3,sp
    adds r3,#1
    bl enter
    str r0,[sp,#100]
    ldr r2,display_control
    ldrh r2,[r2]
    lsls r2,#23
    bpl done
    ldr r0,display_map
    movs r1,#1
    lsls r1,#10
    mov r3,sp
    adds r3,#1
    bl enter
    ldr r0,[sp,#100]
    movs r1,#0
done:
    add sp,#112
    pop {r4}
    pop {r3}
    bx r3
enter:
    bx r3
    .balign 4,0
source: .word SCAN_THUMB
display_control: .word 0x03000010
display_map: .word 0x0600f800

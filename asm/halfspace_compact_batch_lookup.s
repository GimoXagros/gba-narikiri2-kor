/* Private compositor cache. R8 points to this call's24byte pin record.
 * Generic native cache stays byte-identical. Native helper stack layout20B.
 */
batch_cache:
    push {r1-r3,lr}
    mov r3,r8
    ldr r3,[r3,#12]
    adds r3,#1
    bne enabled
    bl NATIVE_CACHE
    pop {r1-r3,pc}
enabled:
    bl lookup
    bl MARK_RETURNED
    pop {r1-r3,pc}
lookup:
    push {r4-r7,lr}
    sub sp,#20
    adds r4,r0,#0
    ldr r0,map_global
    ldmia r0!,{r1-r3}
    ldr r0,font_base
    subs r2,r2,r0
    orrs r2,r3
    bne failure
    ldr r0,display_map
    cmp r1,r0
    bne failure
    ldr r0,palette
    ldrb r0,[r0]
    cmp r0,#0
    beq profile
    cmp r0,#11
    bne failure
profile:
    ldr r0,display_control
    ldrh r0,[r0]
    movs r1,#7
    ands r0,r1
    cmp r0,#1
    beq battle
    movs r0,#188
    lsls r0,#1
    movs r1,#72
    b save_profile
battle:
    movs r0,#160
    lsls r0,#1
    movs r1,#64
save_profile:
    str r0,[sp,#12]
    str r1,[sp,#16]
    ldr r1,[r4,#12]
    ldr r2,[sp,#16]
    ldr r5,[sp,#12]
    lsls r5,#5
    ldr r0,font_base
    adds r5,r5,r0
match:
    ldr r7,[r5,#12]
    cmp r1,r7
    bne next
    bl NATIVE_COMPARE_REST
next:
    adds r5,#32
    subs r2,#1
    bne match
    bl ALLOCATE
failure:
    movs r0,#0
    mvns r0,r0
    bl NATIVE_DONE
    .balign 4,0
map_global: .word 0x0300004c
font_base: .word 0x0600c000
display_map: .word 0x0600f800
palette: .word 0x0300145a
display_control: .word 0x03000010

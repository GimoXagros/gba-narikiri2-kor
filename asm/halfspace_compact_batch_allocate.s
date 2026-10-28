/* Bitmap lifetime ends before every wrap/native getter. All returned slots
 * are conservatively added; a full cached set forces one fresh exact scan.
 */
allocate:
    mov r7,r8
    ldr r0,[sp,#12]
    ldr r1,[r7,#12]
    cmp r0,r1
    bne build
    ldr r0,[sp,#16]
    ldr r1,[r7,#16]
    cmp r0,r1
    bne build
    mov r0,sp
    ldmia r7!,{r1-r3}
    stmia r0!,{r1-r3}
    b free_begin
build:
    ldr r2,[sp,#16]
    lsls r0,r2,#22
    mov r12,r0
    ldr r5,[sp,#12]
    lsls r5,#22
    movs r0,#0
    str r0,[sp]
    str r0,[sp,#4]
    str r0,[sp,#8]
    ldr r0,shadow
    movs r1,#160
    lsls r1,#2
    bl NATIVE_MARK_LIVE
    ldr r0,display_control
    ldrh r0,[r0]
    lsrs r0,#9
    bcc seed
    ldr r0,display_map
    movs r1,#1
    lsls r1,#10
    bl NATIVE_MARK_LIVE
seed:
    mov r7,r8
    mov r0,sp
    ldmia r0!,{r1-r3}
    stmia r7!,{r1-r3}
    ldr r0,[sp,#12]
    str r0,[r7]
    ldr r0,[sp,#16]
    str r0,[r7,#4]
    movs r7,#0
free_begin:
    movs r6,#0
free_slot:
    bl NATIVE_SLOT_IS_LIVE
    beq copy
    adds r6,#1
    ldr r0,[sp,#16]
    cmp r6,r0
    blo free_slot
    cmp r7,#0
    bne build
    movs r0,#0
    mvns r0,r0
    bl NATIVE_DONE
copy:
    bl NATIVE_COPY_SETUP
    .balign 4,0
shadow: .word 0x03000058
display_control: .word 0x03000010
display_map: .word 0x0600f800

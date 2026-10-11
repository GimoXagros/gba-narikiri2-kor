/* ARMv4T Thumb bridge for a caller whose BL cannot reach the runtime bundle.
 * Place only in a verified, unconsumed 16-byte ROM range. It preserves r0-r3
 * and r4, including the SELECT_JOB table pointer in r3. The literal is a
 * link-time relocation; never ship the marker below unchanged.
 */
strict_runtime_select_job_near_veneer:
    push {r4}
    ldr r4, strict_runtime_select_job_far_target
    mov ip, r4
    pop {r4}
    bx ip
    nop
strict_runtime_select_job_far_target: .word 0xDE5C0003

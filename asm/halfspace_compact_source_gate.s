/* r0 is the resolved original identity, never the decoded RAM copy.
 * Reuse the frozen exact-start directories; exclude keyboard and SELECT16.
 */
    push {r4,lr}
    movs r4,r0
    lsrs r1,r4,#24
    cmp r1,#8
    beq native_bank
    ldr r1,arte_source
    eors r1,r4
    movs r2,#25
    rors r1,r2
    cmp r1,#2
    bhi absent
    ldr r4,arte_source
    b rom
native_bank:
    ldr r1,arte_source
    cmp r4,r1
    beq absent
rom:
    ldr r0,select_start
    subs r0,r4,r0
    ldr r1,select_span
    cmp r0,r1
    bls absent
    ldr r2,exclusions
    movs r3,#SOURCE_EXCLUSION_COUNT
exclude:
    ldmia r2!,{r0}
    cmp r0,r4
    beq absent
    subs r3,#1
    bne exclude
    movs r0,r4
    bl COMPACT_SOURCE_LOOKUP
    b done
absent:
    movs r0,#0
done:
    pop {r4}
    pop {r3}
    bx r3
    .balign 4,0
arte_source: .word 0x082bcfe0
select_start: .word 0x082c7c08
select_span: .word 0x00000a04
exclusions: .word SOURCE_EXCLUSIONS

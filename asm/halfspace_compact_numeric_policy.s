/* Private marked template only: r0=copy,r1=bytes,r2=original ROM identity.
 * Table entries: source u32, numeric separator u8, compensating halfspaces u8.
 * Preserve the 8px column separator; restore pixels removed inside its label.
 */
    push {r4-r7,lr}
    movs r4,r0
    ldr r3,policy
    ldr r5,[r3]
    cmp r2,r5
    blo good
    ldr r5,[r3,#88]
    cmp r2,r5
    bhi good
    movs r5,#12
search:
    ldr r0,[r3]
    cmp r0,r2
    beq found
    adds r3,#8
    subs r5,#1
    bne search
    b good
found:
    ldrb r6,[r3,#4]
    adds r0,r6,#1
    cmp r0,r1
    bhs bad
    ldrb r7,[r3,#5]
    adds r0,r1,r7
    movs r2,#72
    lsls r2,#2
    cmp r0,r2
    bhi bad
    ldrb r0,[r4,r6]
    cmp r0,#31
    beq restore
    cmp r0,#32
    bne bad
restore:
    movs r0,#32
    strb r0,[r4,r6]
    cmp r7,#0
    beq good
    /* The immutable policy has at most one compensating halfspace. */
    cmp r7,#1
    bne bad
    movs r2,r1
    adds r6,#1
shift:
    subs r0,r2,#1
    ldrb r3,[r4,r0]
    strb r3,[r4,r2]
    movs r2,r0
    cmp r2,r6
    bhi shift
    movs r0,#31
    strb r0,[r4,r6]
    adds r1,#1
good:
    movs r0,#1
    b done
bad:
    movs r0,#0
done:
    pop {r4-r7}
    pop {r3}
    bx r3
    .balign 4,0
policy: .word NUMERIC_POLICY

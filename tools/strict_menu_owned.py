"""Owned menu-table adapter for six static and one bounded dynamic menu.

No ROM is patched by this module.  The wrapper recognizes exact original
table addresses or the exact stack-table caller at 0801C354, allocates one
heap object containing a pointer table and native strings, and keeps it alive
until 08004D98 returns. Every other ROM or RAM table goes through the native
callee with its original pointer intact.
The separate 201-entry SELECT_JOB caller wrapper remains authoritative.
"""
from __future__ import annotations

import csv
import json
import struct
from dataclasses import dataclass
from pathlib import Path

ROM_BASE = 0x08000000
MENU_ENTRY = 0x08004D98
MENU_RESUME = 0x08004DA9
HEAP_ALLOC = 0x08003521
HEAP_FREE = 0x080035DD
JP_ENTRY_BYTES = bytes.fromhex("f0b557464e464546e0b484b082460391")
DYNAMIC_CALL_RETURN = 0x0801C359
DYNAMIC_MAX_COUNT = 13
DYNAMIC_MAX_NATIVE_BYTES = DYNAMIC_MAX_COUNT * 17
DYNAMIC_RECORDS = 0x082C7B60
DYNAMIC_COPY_LITERAL = 0x0801C334
DYNAMIC_CALL = 0x0801C354


@dataclass(frozen=True)
class Table:
    name: str
    pointer: int
    count: int
    native_bytes: int
    corpus: str

    @property
    def allocation(self) -> int:
        return (self.count + 1) * 4 + self.native_bytes


TABLES = (
    Table("SELECT_PARTY", 0x083AE0C0, 7, 44, "historical_compact"),
    Table("SELECT_MONSTER", 0x083AE408, 164, 2191, "historical_compact"),
    Table("SELECT_ENEMY", 0x083AE69C, 7, 44, "historical_compact"),
    Table("BATTLE_COMMAND_4", 0x083AE8E0, 4, 69, "additional_ui"),
    Table("BATTLE_COMMAND_3", 0x083AE92C, 3, 24, "additional_ui"),
    Table("BATTLE_COMMAND_5", 0x083AE93C, 5, 93, "additional_ui"),
)


def descriptor_bytes(tables: tuple[Table, ...] = TABLES) -> bytes:
    if not tables or len({t.pointer for t in tables}) != len(tables):
        raise ValueError("Menu table dispatcher needs distinct exact sources")
    if any(t.pointer & 3 or not 1 <= t.count <= 255 or
           not 1 <= t.native_bytes <= 0xFFFF or t.allocation > 0xFFFF
           for t in tables):
        raise ValueError("Menu table count, arena or alignment contract")
    return b"".join(struct.pack("<IHH", t.pointer, t.count, t.native_bytes)
                    for t in tables)


WRAPPER_SOURCE = r"""
strict_menu_owned:
    push {r4-r7,lr}
    sub sp,#28
    str r0,[sp]
    str r1,[sp,#4]
    str r2,[sp,#8]
    str r3,[sp,#12]
    mov r4,r3
    ldr r5,descriptors
    movs r6,#TABLE_COUNT
dispatch:
    ldr r0,[r5]
    cmp r4,r0
    beq selected
    adds r5,#8
    subs r6,#1
    bne dispatch
    b dynamic_source
dynamic_source:
    ldr r0,[sp,#44]
    ldr r1,dynamic_return
    cmp r0,r1
    bne passthrough
    movs r0,#0
    mov r5,r4
dynamic_count:
    ldr r1,[r5]
    cmp r1,#0
    beq dynamic_ready
    cmp r0,#DYNAMIC_MAX_COUNT
    beq cancelled
    adds r5,#4
    adds r0,#1
    b dynamic_count
dynamic_ready:
    cmp r0,#0
    beq passthrough
    str r0,[sp,#20]
    movs r6,#DYNAMIC_MAX_NATIVE_BYTES
    b allocate
selected:
    ldrh r0,[r5,#4]
    str r0,[sp,#20]
    ldrh r6,[r5,#6]
allocate:
    adds r0,#1
    lsls r0,r0,#2
    adds r0,r0,r6
    bcs cancelled
    str r0,[sp,#16]
    ldr r3,heap_alloc
    bl call_r3
    mov r7,r0
    cmp r7,#0
    beq cancelled
    ldr r0,[sp,#16]
    adds r0,r7,r0
    bcs free_cancel
    str r0,[sp,#16]
    mov r5,r7
    ldr r0,[sp,#20]
    adds r0,#1
    lsls r0,r0,#2
    adds r6,r7,r0
stage_loop:
    ldr r0,[r4]
    cmp r0,#0
    beq free_cancel
    mov r1,r6
    ldr r2,[sp,#16]
    subs r2,r2,r6
    ldr r3,owned_decoder
    bl call_r3
    cmp r0,r6
    bne free_cancel
    cmp r1,r6
    bne free_cancel
    cmp r2,#0
    beq free_cancel
    str r6,[r5]
    adds r6,r6,r2
    bcs free_cancel
    adds r4,#4
    adds r5,#4
    ldr r0,[sp,#20]
    subs r0,#1
    str r0,[sp,#20]
    bne stage_loop
    ldr r0,[r4]
    cmp r0,#0
    bne free_cancel
    movs r0,#0
    str r0,[r5]
    ldr r0,[sp]
    ldr r1,[sp,#4]
    ldr r2,[sp,#8]
    mov r3,r7
    ldr r4,original_menu
    bl call_r4
    mov r5,r0
    mov r0,r7
    ldr r3,heap_free
    bl call_r3
    mov r0,r5
    b finished
passthrough:
    ldr r0,[sp]
    ldr r1,[sp,#4]
    ldr r2,[sp,#8]
    ldr r3,[sp,#12]
    ldr r4,original_menu
    bl call_r4
    b finished
free_cancel:
    mov r0,r7
    ldr r3,heap_free
    bl call_r3
cancelled:
    movs r0,#1
    rsbs r0,r0,#0
finished:
    add sp,#28
    pop {r4-r7}
    pop {r3}
    bx r3
call_r3:
    bx r3
call_r4:
    bx r4
    .balign 4,0
descriptors: .word DESCRIPTOR_ADDRESS
owned_decoder: .word DECODER_ADDRESS
original_menu: .word ORIGINAL_ADDRESS
heap_alloc: .word 0x08003521
heap_free: .word 0x080035dd
dynamic_return: .word DYNAMIC_RETURN
"""


def assemble_wrapper(address: int, *, descriptor_address: int,
                     decoder: int, original_menu: int,
                     tables: tuple[Table, ...] = TABLES) -> bytes:
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    if address & 3 or descriptor_address & 3 or any(
            not pointer & 1 for pointer in (decoder, original_menu)):
        raise ValueError("Thumb adapter and descriptor alignment")
    descriptor_bytes(tables)
    source = (WRAPPER_SOURCE.replace("TABLE_COUNT", str(len(tables)))
             .replace("DYNAMIC_MAX_COUNT", str(DYNAMIC_MAX_COUNT))
             .replace("DYNAMIC_MAX_NATIVE_BYTES", str(DYNAMIC_MAX_NATIVE_BYTES))
             .replace("DYNAMIC_RETURN", str(DYNAMIC_CALL_RETURN)))
    for name, value in (("DESCRIPTOR_ADDRESS", descriptor_address),
                        ("DECODER_ADDRESS", decoder),
                        ("ORIGINAL_ADDRESS", original_menu)):
        source = source.replace(name, str(value))
    code = bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source, addr=address)[0])
    # Thumb-1 only: the output starts at an aligned ROM address and all
    # transfer targets are explicit Thumb pointers in the final literal pool.
    if code[:2] != bytes.fromhex("f0b5") or any(
            ins.mnemonic in {"blx", "it", "movw", "movt"}
            for ins in Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(code, address)):
        raise ValueError("Menu wrapper changed ARMv4T instruction profile")
    return code


def assemble_entry_patch(wrapper: int) -> bytes:
    """16-byte callee entry jump preserving live r0-r3 and original LR."""
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
    if not wrapper & 1:
        raise ValueError("Thumb wrapper required")
    source = f"""
        push {{r4}}
        ldr r4,target
        mov ip,r4
        pop {{r4}}
        bx ip
        .balign 4,0
    target: .word {wrapper}
    """
    patch = bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source, addr=MENU_ENTRY)[0])
    if len(patch) != 16 or patch[-4:] != struct.pack("<I", wrapper):
        raise ValueError("Menu entry patch extent or literal changed")
    return patch


def assemble_trampoline(address: int, japanese: bytes | None = None) -> bytes:
    """Replay the exact overwritten prologue, then resume at 08004DA8."""
    from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
    if address & 3:
        raise ValueError("Menu trampoline alignment")
    source = f"""
        push {{r4-r7,lr}}
        mov r7,sl
        mov r6,sb
        mov r5,r8
        push {{r5,r6,r7}}
        sub sp,#16
        mov sl,r0
        str r1,[sp,#12]
        ldr r4,resume
        bx r4
        .balign 4,0
    resume: .word {MENU_RESUME}
    """
    code = bytes(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm(source, addr=address)[0])
    if japanese is not None:
        if len(japanese) != 0x800000 or japanese[MENU_ENTRY-ROM_BASE:MENU_ENTRY-ROM_BASE+16] != code[:16]:
            raise ValueError("Menu original prologue differs from trampoline")
    return code


def verify_tables(japanese: bytes, probe: bytes, historical: list[dict],
                  fits: list[dict], extra_rows: list[dict],
                  tables: tuple[Table, ...] = TABLES) -> dict:
    """Prove exact source table, terminator, binding and native-size census."""
    if len(japanese) != 0x800000 or len(probe) < len(japanese):
        raise ValueError("Exact source size required")
    if japanese[MENU_ENTRY-ROM_BASE:MENU_ENTRY-ROM_BASE+16] != probe[MENU_ENTRY-ROM_BASE:MENU_ENTRY-ROM_BASE+16]:
        raise ValueError("Adopted menu entry changed before hook")
    bound = {int(row["jp_pointer_storage"]): row for row in historical}
    fit = {row["binding_id"]: row for row in fits}
    extra = {row["storage"]: row for row in extra_rows}
    output = []
    for table in tables:
        start = table.pointer - ROM_BASE
        native_total = 0
        for index in range(table.count):
            storage = start+4*index
            original = struct.unpack_from("<I", japanese, storage)[0]
            current = struct.unpack_from("<I", probe, storage)[0]
            if not ROM_BASE <= original < ROM_BASE+len(japanese) or current != original:
                raise ValueError(f"{table.name}: original pointer changed at {index}")
            if table.corpus == "historical_compact":
                row = bound.get(storage)
                if row is None or row["category"] != "compact":
                    raise ValueError(f"{table.name}: missing compact binding {index}")
                record = fit[row["binding_id"]]
                if record["inline_part_count"] != "1" or record["inline_selection"] != "1":
                    raise ValueError(f"{table.name}: context alias requires own adapter")
                native_total += int(record["native_output_length"])
            elif table.corpus == "additional_ui":
                row = extra.get(storage)
                if row is None or row["start"] + ROM_BASE != original:
                    raise ValueError(f"{table.name}: missing additional UI {index}")
                native_total += len(bytes.fromhex(row["native_hex"])) + 1
            else:
                raise ValueError("Unknown menu corpus")
        if struct.unpack_from("<I", japanese, start+4*table.count)[0] != 0 or (
                struct.unpack_from("<I", probe, start+4*table.count)[0] != 0):
            raise ValueError(table.name + ": table sentinel changed")
        if native_total != table.native_bytes:
            raise ValueError(table.name + ": exact native arena changed")
        output.append(dict(name=table.name, pointer=table.pointer,
                           count=table.count, native_bytes=native_total,
                           heap_bytes=table.allocation,
                           original_pointer_bytes_unchanged=True))
    return dict(status="STATIC_MENU_SOURCE_AND_HEAP_SIZE_PROVED_NO_HOOK_INSTALLED",
                table_count=len(output), tables=output,
                dynamic_stack_menu="0801C354_HANDLED_SEPARATELY",
                other_native_ram_tables="PASSTHROUGH_UNCHANGED")


def verify_dynamic_source(japanese: bytes, probe: bytes,
                          historical: list[dict], fits: list[dict]) -> dict:
    """Guard the 13 compact records copied into 0801C354's stack table.

    The table is a filtered subset of the source records, so its 14th word
    is always the NUL sentinel. The heap allocation uses a 17B bound for
    each of the 13 possible native strings even if a subset is selected.
    """
    if len(japanese) != 0x800000 or len(probe) < len(japanese):
        raise ValueError("Exact source size required")
    code_start, code_end = 0x1C2CC, 0x1C360
    if japanese[code_start:code_end] != probe[code_start:code_end]:
        raise ValueError("Dynamic menu copy/call code changed")
    if struct.unpack_from("<I", japanese,
                          DYNAMIC_COPY_LITERAL-ROM_BASE)[0] != DYNAMIC_RECORDS:
        raise ValueError("Dynamic menu source literal changed")
    if japanese[DYNAMIC_CALL-ROM_BASE:DYNAMIC_CALL-ROM_BASE+4] != bytes.fromhex("e8f720fd"):
        raise ValueError("Dynamic menu callsite changed")
    start = DYNAMIC_RECORDS-ROM_BASE
    if japanese[start:start+8*(DYNAMIC_MAX_COUNT+1)] != (
            probe[start:start+8*(DYNAMIC_MAX_COUNT+1)]):
        raise ValueError("Dynamic record pointers/handlers changed")
    bound = {int(row["jp_pointer_storage"]): row for row in historical}
    fit = {row["binding_id"]: row for row in fits}
    outputs = []
    for index in range(DYNAMIC_MAX_COUNT):
        storage = start+8*index
        pointer, handler = struct.unpack_from("<II", japanese, storage)
        row = bound.get(storage)
        if not ROM_BASE <= pointer < ROM_BASE+len(japanese) or not handler & 1:
            raise ValueError("Dynamic record is not text/Thumb handler")
        if row is None or row["category"] != "compact" or (
                row["jp_pointer_value"] != str(pointer)):
            raise ValueError("Dynamic record lacks its compact binding")
        record = fit[row["binding_id"]]
        if record["inline_part_count"] != "1" or record["inline_selection"] != "1":
            raise ValueError("Dynamic record requires context alias")
        length = int(record["native_output_length"])
        if not 1 <= length <= 17:
            raise ValueError("Dynamic native entry exceeds 17B bound")
        outputs.append(length)
    if japanese[start+8*DYNAMIC_MAX_COUNT:start+8*(DYNAMIC_MAX_COUNT+1)] != b"\0"*8:
        raise ValueError("Dynamic record sentinel changed")
    if sum(outputs) != 152:
        raise ValueError("Dynamic source native sum changed")
    return dict(status="DYNAMIC_STACK_SOURCE_BOUND_PROVED_NO_HOOK_INSTALLED",
                call=DYNAMIC_CALL, source_records=DYNAMIC_RECORDS,
                count=DYNAMIC_MAX_COUNT, native_lengths=outputs,
                native_bytes_sum=sum(outputs), native_bytes_allocated=DYNAMIC_MAX_NATIVE_BYTES,
                heap_bytes_max=(DYNAMIC_MAX_COUNT+1)*4+DYNAMIC_MAX_NATIVE_BYTES,
                original_stack_table_unchanged=True)

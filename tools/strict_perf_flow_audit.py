"""Inspect reachable direct Thumb flow and PC literals in six fixed owners.

This is a bounded static inventory, not an indirect-target or bus-safety proof.
Only immutable known image inputs are accepted. No assembler is imported.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

BASE = 0x08000000
OWNERS = {
    'owned': (0xB9C00, 0xB9D3C, [0xB9C00, 0xB9C08]),
    'lookup': (0xB9D3C, 0xB9DE4, [0xB9D3C]),
    'tile': (0xC5BA8, 0xC5E50, [0xC5BA8]),
    'full_draw': (0xCAA10, 0xCAB58, [0xCAA10, 0xCAA18]),
    'unit': (0x37E1F0, 0x37E336, [0x37E1F0]),
    'gap': (0x3A8464, 0x3A8520, [0x3A8464]),
}
CONDITIONAL = {'beq', 'bne', 'bhs', 'blo', 'bcs', 'bcc', 'bmi', 'bpl',
               'bvs', 'bvc', 'bhi', 'bls', 'bge', 'blt', 'bgt', 'ble'}
CS = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

def require(value, message):
    if not value:
        raise ValueError(message)

def inventory(rom):
    rows = []
    for name, (start, end, entries) in OWNERS.items():
        todo = entries[:]
        seen = {}
        literals = {}
        branches = []
        adr = []
        exits = []
        while todo:
            at = todo.pop()
            if at in seen:
                continue
            require(start <= at < end and at % 2 == 0, (name, 'branch outside owner', hex(at)))
            ins = next(CS.disasm(rom[at:at+4], BASE+at, count=1), None)
            require(ins is not None and ins.size in (2,4), (name, 'invalid Thumb instruction', hex(at)))
            require(ins.size == 2 or ins.mnemonic == 'bl', (name, 'Non-ARM7 wide Thumb instruction', hex(at)))
            require(ins.mnemonic not in {'cbz','cbnz','cpsid','cpsie','rev','rev16','revsh',
                    'sxth','sxtb','uxth','uxtb','setend','sev','yield','wfe','wfi','nop'}
                    and not ins.mnemonic.startswith('it'), (name, 'Post-ARM7 Thumb instruction', hex(at)))
            require(at + ins.size <= end, (name, 'instruction crosses owner'))
            seen[at] = dict(address=hex(BASE+at), size=ins.size, mnemonic=ins.mnemonic, operands=ins.op_str)
            half = struct.unpack_from('<H', rom, at)[0]
            if half & 0xF800 == 0x4800:
                pool = ((at+4)&~3) + (half&255)*4
                require(start <= pool <= end-4, (name, 'PC literal outside owner', hex(pool)))
                value = struct.unpack_from('<I', rom, pool)[0]
                row = literals.setdefault(pool, {'storage':hex(BASE+pool), 'value':hex(value), 'sites':[]})
                row['sites'].append(hex(BASE+at))
            if half & 0xF800 == 0xA000:
                target = ((at+4)&~3) + (half&255)*4
                require((half >> 8) & 7 == 3 and at + 4 <= end,
                        (name, 'Unexpected ADR register or consumer'))
                consumer = struct.unpack_from('<H', rom, at+2)[0]
                require(consumer in (0xCB61, 0xCB60), (name, 'Unexpected ADR LDM consumer'))
                if name == 'owned' and at == 0xB9C7A:
                    require(consumer == 0xCB60, 'Compact profile must read exactly two words')
                span = 12 if consumer == 0xCB61 else 8
                if span == 8:
                    require(name == 'owned' and at == 0xB9C7A and target == 0xB9D14
                            and struct.unpack_from('<H', rom, at-2)[0] == 0x201D,
                            (name, 'Unexpected compact immediate-capacity profile'))
                require(start <= target and target + span <= end, (name, 'ADR profile outside owner', hex(target)))
                adr.append({'site':hex(BASE+at),'target':hex(BASE+target),
                            'span_bytes':span, 'consumer_halfword':hex(consumer),
                            'words':[hex(x) for x in struct.unpack_from('<'+'I'*(span//4),rom,target)]})
            if ins.mnemonic in CONDITIONAL | {'b', 'bl'}:
                target = int(ins.op_str.replace('#',''),0)-BASE
                branches.append({'site':hex(BASE+at),'target':hex(BASE+target),'kind':ins.mnemonic})
                require(start <= target < end, (name, 'direct external branch', hex(at), hex(target)))
                inline_compact = name == 'owned' and rom[0xB9C7A:0xB9C7C] == b'\x26\xa3'
                require(not inline_compact or target not in (0xB9C7A, 0xB9C7C),
                        (name, 'Direct branch bypasses compact profile setup'))
                todo.append(target)
                if ins.mnemonic != 'b':
                    todo.append(at+ins.size)
                continue
            if ins.mnemonic == 'bx' or (ins.mnemonic == 'pop' and 'pc' in ins.op_str):
                exits.append(seen[at])
                continue
            require(not ('pc' in ins.op_str and ins.mnemonic not in ('ldr','adr','add')), (name,'unclassified PC use', seen[at]))
            todo.append(at+ins.size)
        byte_owner = {}
        for at, ins in seen.items():
            for b in range(at,at+ins['size']):
                require(b not in byte_owner, (name,'branch to middle of instruction',hex(at)))
                byte_owner[b]=at
        for pool in literals:
            require(all(b not in byte_owner for b in range(pool,pool+4)), (name,'executable literal overlap',hex(pool)))
        for item in adr:
            target=int(item['target'],16)-BASE
            require(all(b not in byte_owner for b in range(target,target+item['span_bytes'])), (name,'executable ADR data overlap'))
            if item['span_bytes'] == 8:
                site=int(item['site'],16)
                require(all(int(b['target'],16) not in (site,site+2) for b in branches),
                        (name,'Branch bypasses compact immediate capacity'))
        rows.append({'name':name,'start':hex(BASE+start),'end_exclusive':hex(BASE+end),
                     'entries':[hex(BASE+x) for x in entries],
                     'instruction_count':len(seen),'instruction_bytes':len(byte_owner),
                     'literals':sorted(literals.values(),key=lambda x:x['storage']),
                     'adr_data':adr,'direct_branches':branches,'indirect_exits':exits,
                     'instructions':[seen[x] for x in sorted(seen)]})
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--rom',type=Path,required=True)
    ap.add_argument('--sha256',required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    data=a.rom.read_bytes()
    require(len(data)==0x800000,'Exact 8MiB required')
    digest=hashlib.sha256(data).hexdigest()
    require(digest==a.sha256,'Input identity')
    rows=inventory(data)
    report={'status':'BOUNDED_DIRECT_FLOW_INVENTORY','sha256':digest,'bytes':len(data),'owners':rows,
            'qualification':'Direct reachability only; indirect BX destinations and literal ownership require separate contracts. Not complete game reachability, bus-safety, or performance evidence.'}
    a.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{k:v for k,v in r.items() if k not in ('instructions','direct_branches','indirect_exits')} for r in rows],indent=2))
if __name__=='__main__':main()

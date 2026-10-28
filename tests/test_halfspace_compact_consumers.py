import hashlib
import sys
import unittest
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from halfspace_compact_consumers import lexical_offsets, marked_copy, prepared_copy, source_plan, NUMERIC_COLUMNS


class CompactOriginPolicy(unittest.TestCase):
    def test_numeric_alignment_preserves_column_and_narrows_label(self):
        glyph=b'\x7f\x01\x01'
        raw=glyph*2+b' '+glyph*3+b' %7d\0'
        binding='EXTRA_UI:0001465C'
        actual=prepared_copy(binding,raw,0x082c4674)
        self.assertEqual(actual,glyph*2+b'\x1f'+glyph*3+b' \x1f%7d\0')
        self.assertEqual(raw,glyph*2+b' '+glyph*3+b' %7d\0')
        # Two original 8px blanks become 4px lexical + 12px alignment padding.
        self.assertEqual(8+8,4+8+4)
        for source in (0x02001000,0x082c4678):
            with self.assertRaises(ValueError):prepared_copy(binding,raw,source)
        with self.assertRaises(ValueError):prepared_copy(binding,raw.replace(b'%7d',b'XYZ'),0x082c4674)
        self.assertEqual(prepared_copy('EXTRA_UI:00010DD4',glyph*2+b' %7d\0',0x082c3d10),glyph*2+b' %7d\0')

    def test_variable_separator_but_not_padding_or_keyboard(self):
        tokens = [b'%', b's', b' ', b'\x7f\x01\x01']
        self.assertEqual(lexical_offsets('EXTRA_UI:test', tokens), [2])
        self.assertEqual(marked_copy(b'%s '+tokens[-1]+b'\0', [2]), b'%s\x1f'+tokens[-1]+b'\0')
        glyph = tokens[-1]
        aligned = [glyph, b' ', b' ', b'%', b'4', b'd']
        self.assertEqual(lexical_offsets('EXTRA_UI:test', aligned), [])
        self.assertEqual(lexical_offsets('EXTRA_UI:003A7A70', tokens), [])

    def test_markers_cannot_change_input_controls_or_create_ambiguity(self):
        for raw, offsets in [(b'A B\0', [0]), (b'A B\0', [1, 1]),
                             (b'A B\0', [-1]), (b'A\x1fB\0', []), (b'A\0B\0', []),
                             (b'\x7f\x20\x01\0', [1])]:
            with self.subTest(raw=raw, offsets=offsets), self.assertRaises(ValueError):
                marked_copy(raw, offsets)
        original = b'A B  C\0'
        result = marked_copy(original, [1])
        self.assertEqual(result, b'A\x1fB  C\0')
        self.assertEqual(original, b'A B  C\0')
        self.assertEqual(marked_copy(b'\x7f\x01\x1f B\0', [3]), b'\x7f\x01\x1f\x1fB\0')


class NativeMarkerComponent(unittest.TestCase):
    """CPU component checks; no installed hook or consumer approval is implied."""
    def setUp(self):
        from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
        from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB
        self.root=Path(__file__).resolve().parents[1]
        source=(self.root/'asm/halfspace_compact_consumers_mark.s').read_text(encoding='utf-8')
        code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,addr=0x02020000)[0])
        self.assertLessEqual(len(code),144)
        self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        self.cpu.mem_map(0x02000000,0x40000)
        self.cpu.mem_write(0x02020000,code)

    def run_copy(self,raw,capacity=None,arm_return=False):
        from unicorn.arm_const import (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R4,
            UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_CPSR)
        cpu=self.cpu;dest=0x02001000
        cpu.mem_write(dest-16,b'\xa5'*352)
        cpu.mem_write(dest,raw)
        for reg,value in ((UC_ARM_REG_R0,dest),(UC_ARM_REG_R1,len(raw) if capacity is None else capacity),
            (UC_ARM_REG_R4,0x12341234),(UC_ARM_REG_R5,0x23452345),(UC_ARM_REG_R6,0x34563456),
            (UC_ARM_REG_SP,0x0203f000),(UC_ARM_REG_LR,0x02030000 if arm_return else 0x02030001)):
            cpu.reg_write(reg,value)
        cpu.emu_start(0x02020001,0x02030000,count=30000)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_PC),0x02030000)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_SP),0x0203f000)
        for reg,value in ((UC_ARM_REG_R4,0x12341234),(UC_ARM_REG_R5,0x23452345),(UC_ARM_REG_R6,0x34563456)):
            self.assertEqual(cpu.reg_read(reg),value)
        self.assertEqual(bool(cpu.reg_read(UC_ARM_REG_CPSR)&32),not arm_return)
        self.assertEqual(bytes(cpu.mem_read(dest-16,16)),b'\xa5'*16)
        self.assertEqual(bytes(cpu.mem_read(dest+len(raw),336-len(raw))),b'\xa5'*(336-len(raw)))
        return cpu.reg_read(UC_ARM_REG_R0),bytes(cpu.mem_read(dest,len(raw)))

    def test_atomic_rejection_and_token_boundaries(self):
        for raw,capacity in [(b'A B',3),(b'A\0B\0',4),(b'A B\0',0),(b'A B\0',289),
                              (b'A B\x1fC\0',6),(b'A B\x7f\x01\0',6),
                              (b'A B\x7f\x20\x01\0',7)]:
            self.assertEqual(self.run_copy(raw,capacity),(0,raw))
        for arm in (False,True):
            raw=b' A B  C\nD E \x7f\x01\x1f F \0'
            expected=b' A\x1fB  C\nD\x1fE\x1f\x7f\x01\x1f\x1fF \0'
            self.assertEqual(self.run_copy(raw,arm_return=arm),(1,expected))

    def test_glyph_length_addition_cannot_wrap_before_validation(self):
        from unicorn import UC_HOOK_MEM_READ
        from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
        self.cpu.mem_map(0xfffff000,0x1000)
        self.cpu.mem_write(0xfffffffc,b'A\x7f\x01\x01')
        reads=[]
        self.cpu.hook_add(UC_HOOK_MEM_READ,lambda cpu,access,address,size,value,data: reads.append((address,size)))
        for reg,value in ((UC_ARM_REG_R0,0xfffffffc),(UC_ARM_REG_R1,3),
                          (UC_ARM_REG_SP,0x0203f000),(UC_ARM_REG_LR,0x02030001)):
            self.cpu.reg_write(reg,value)
        self.cpu.emu_start(0x02020001,0x02030000,count=30000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_PC),0x02030000)
        self.assertEqual(self.cpu.reg_read(UC_ARM_REG_R0),0)
        self.assertTrue(all(address>=0x02000000 and address+size<=0xffffffff for address,size in reads))
        self.assertEqual(bytes(self.cpu.mem_read(0xfffffffc,4)),b'A\x7f\x01\x01')

    def test_exact_corpus_markers_match_reviewed_source_plan(self):
        from halfspace_compact import compact_rows,KEYBOARD
        from strict_unit_codec import units
        old=self.root.parent/'narikiri2-v09d-graphics-test/private_validation'
        stage=old/'v11-runtime-20261003/stage4-integrated-source-a-20261011'
        paths=[self.root/'private_validation/halfspace-graphics-20261025/runtime/BASE_v11a.gba',
               old/'kr-patch-qa-20261019/reviewed-dialogue-data.json',stage/'linked/LINK.json',
               stage/'components/BUILD.json']
        if not all(p.exists() for p in paths):self.skipTest('Private exact source inputs unavailable')
        rows=compact_rows(paths[0].read_bytes(),*[json.loads(p.read_text(encoding='utf-8')) for p in paths[1:]])
        checked=markers=emitted=0
        numeric_seen=set()
        for row,tokens in rows:
            if row['binding_id'] in KEYBOARD:continue
            raw=b''.join(tokens)+b'\0';offsets=lexical_offsets(row['binding_id'],tokens)
            self.assertEqual(self.run_copy(raw),(1,marked_copy(raw,offsets)),row['binding_id'])
            prepared=prepared_copy(row['binding_id'],raw,0x08000000+int(row['original_start'],16))
            prepared_tokens=units(prepared[:-1],'compact')
            emitted+=prepared_tokens.count(b'\x1f')
            if row['binding_id'] in NUMERIC_COLUMNS:
                numeric_seen.add(row['binding_id'])
                old_prefix=tokens[:tokens.index(b'%')]
                new_prefix=prepared_tokens[:prepared_tokens.index(b'%')]
                self.assertEqual(len(old_prefix)*8,sum(4 if t==b'\x1f' else 8 for t in new_prefix))
                self.assertEqual(raw[raw.index(b'%'):],prepared[prepared.index(b'%'):])
            checked+=1;markers+=len(offsets)
        # Two of the nine keyboard storages use the full-name book, outside this set.
        self.assertEqual((len(rows),checked,markers),(1420,1413,500))
        self.assertEqual(numeric_seen,set(NUMERIC_COLUMNS))
        self.assertEqual(emitted,491)
        plan=source_plan(rows)
        self.assertEqual(sum(len(r['marker_offsets']) for r in plan),488)
        self.assertEqual(sum(r['column_compensation_markers'] for r in plan),3)
        for (row,tokens),record in zip(rows,plan):
            expected=prepared_copy(row['binding_id'],b''.join(tokens)+b'\0',0x08000000+int(row['original_start'],16))
            self.assertEqual(record['transient_sha256'],hashlib.sha256(expected).hexdigest())
            self.assertEqual(record['transient_bytes'],len(expected))


if __name__ == '__main__':
    unittest.main()

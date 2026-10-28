"""Exact pixel preservation, true4px advance and ARM pending lifetime."""
import struct
import json
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from halfspace_compact import compose, pair, proposed_advances, accepted_segments, compact_rows, resolved_hangul, repair_simple_trampoline, compact_overlay, cache_home_overlay, cache_cpu, DRAW, CALLERS, VARARGS_STUB, BATCH_OWNERS
from build_halfspace_prototype import assemble
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import *


class CompactPairTests(unittest.TestCase):
    def test_fixed_user_keyboard_and_control_padding_exceptions(self):
        tokens = [b'\x7f\x01\x01', b' ', b'\x7f\x01\x02']
        for row in ({'category': 'fixed_name', 'binding_id': 'FIXED_NAME'},
                    {'category': 'full_text', 'binding_id': 'EXTRA_UI:00009784'},
                    {'category': 'compact', 'binding_id': 'EXTRA_UI:003A7A70'},
                    {'category': 'compact', 'binding_id': 'EXTRA_UI:003A7A88'}):
            self.assertEqual(proposed_advances(row, tokens), [8, 8, 8])
        row = {'category': 'compact', 'binding_id': 'ITEM_001:002B2CC0'}
        self.assertEqual(proposed_advances(row, tokens), [8, 4, 8])
        for payload in ([b' ', tokens[0]], [tokens[0], b' '], [tokens[0], b' ', b' ', tokens[2]],
                        [b'%', b's', b' ', tokens[2]]):
            widths = proposed_advances(row, payload)
            for n, token in enumerate(payload):
                if token == b' ': self.assertEqual(widths[n], 8)

    def test_actual_arm_pair_preserves_every_nibble_and_callee_register(self):
        code = assemble((ROOT / 'asm/halfspace_compact_pair.s').read_text(encoding='utf-8'), 0x1000)
        for clear in (0, 11):
            for shift in range(16):
                pending = bytes((n + shift) % 256 for n in range(32))
                glyph = bytes((255 - n + shift) % 256 for n in range(32))
                expected, following = pair(pending, glyph, clear)
                cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
                cpu.mem_map(0x08000000, 0x2000)
                cpu.mem_map(0x02000000, 0x40000)
                cpu.mem_write(0x08001000, code)
                cpu.mem_write(0x02001000, b'\xa5' * 128)
                cpu.mem_write(0x02001000, pending)
                cpu.mem_write(0x02001020, glyph)
                saved = {r: 0x12340000 + r for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7)}
                for r, v in saved.items(): cpu.reg_write(r, v)
                for r, v in ((UC_ARM_REG_R0, 0x02001000), (UC_ARM_REG_R1, 0x02001020),
                             (UC_ARM_REG_R2, 0x02001040), (UC_ARM_REG_R3, clear * 0x1111),
                             (UC_ARM_REG_SP, 0x0203f000), (UC_ARM_REG_LR, 0x08000201)):
                    cpu.reg_write(r, v)
                cpu.emu_start(0x08001001, 0x08000200, count=200)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x08000200)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x0203f000)
                self.assertEqual(bytes(cpu.mem_read(0x02001000, 32)), following)
                self.assertEqual(bytes(cpu.mem_read(0x02001020, 32)), glyph)
                self.assertEqual(bytes(cpu.mem_read(0x02001040, 32)), expected)
                self.assertEqual(bytes(cpu.mem_read(0x02001060, 32)), b'\xa5' * 32)
                for r, v in saved.items(): self.assertEqual(cpu.reg_read(r), v)

    def test_true_four_pixel_spacing_and_whole_glyph_shapes(self):
        glyphs = [bytes([n] * 32) for n in (0x12, 0, 0x34, 0x56, 0, 0x78)]
        tiles, width, starts = compose(glyphs, [8, 4, 8, 8, 4, 8])
        self.assertEqual((width, starts), (40, [0, 8, 12, 20, 28, 32]))
        for y in range(8):
            line = b''.join(t[y*4:y*4+4] for t in tiles)
            self.assertEqual(line, b'\x12'*4 + b'\0'*2 + b'\x34'*4 + b'\x56'*4 + b'\0'*2 + b'\x78'*4)

    def test_alignment_spaces_remain_eight_pixels_and_tail_is_cleared(self):
        for clear in (0, 11):
            blank = bytes([clear * 17]) * 32
            glyph = bytes([0xff]) * 32
            tiles, width, starts = compose([blank, glyph, blank, glyph, blank], [8, 8, 4, 8, 8], clear)
            self.assertEqual((width, starts), (36, [0, 8, 16, 20, 28]))
            self.assertEqual(tiles[-1], blank)
            self.assertEqual(compose([glyph, blank], [8, 4], clear)[1], 12)

    def test_unapproved_narrow_glyph_and_invalid_inputs_fail(self):
        for tiles, widths, mode in (([b'\xff'*32], [4], 0), ([bytes(31)], [8], 0),
                                    ([bytes(32)], [], 0), ([bytes(32)], [6], 0),
                                    ([bytes(32)], [8], 1)):
            with self.assertRaises(ValueError): compose(tiles, widths, mode)


class CurrentROMConsumerTests(unittest.TestCase):
    @staticmethod
    def batch_profile(cpu):
        cpu.mem_map(0x04000000, 0x1000)
        for at, value in ((0x03007ffc, 0x03002b40), (0x03002b04, 0x080004b1),
                          (0x03007ff0, 0x02003f00), (0x02003f00, 0x68736d53)):
            cpu.mem_write(at, struct.pack('<I', value))
        cpu.mem_write(0x04000200, b'\x01\x20')

    @classmethod
    def setUpClass(cls):
        baseline = ROOT / 'private_validation/halfspace-graphics-20261025/runtime/BASE_v11a.gba'
        old = ROOT.parent / 'narikiri2-v09d-graphics-test/private_validation'
        link = old / 'v11-runtime-20261003/stage4-integrated-source-a-20261011/linked/LINK.json'
        corpus = old / 'kr-patch-qa-20261019/reviewed-dialogue-data.json'
        components = old / 'v11-runtime-20261003/stage4-integrated-source-a-20261011/components/BUILD.json'
        if not all(p.exists() for p in (baseline, link, corpus, components)):
            raise unittest.SkipTest('Private exact-ROM inputs unavailable')
        cls.image = baseline.read_bytes()
        load = lambda p: json.loads(p.read_text(encoding='utf-8'))
        cls.link, cls.corpus, cls.components = load(link), load(corpus), load(components)
        cls.segments = accepted_segments(cls.image, cls.link)
        converter = assemble((ROOT / 'asm/halfspace_bitmap_convert.s').read_text(encoding='utf-8'), 0x21fc)
        from build_baked_no_c import build as build_c
        prepared = bytearray(build_c(cls.image)[0])
        prepared[0x21fc:0x21fc+len(converter)] = converter
        integrated = ROOT / 'private_validation/halfspace-graphics-20261025/integrated-zc-provisional/Xagros_Narikiri2_KOR_v1.1a_halfspace-graphics-test01.gba'
        if integrated.exists(): prepared = bytearray(integrated.read_bytes())
        cls.candidate, cls.overlay_report = compact_overlay(bytes(prepared), cls.image, cls.link, cls.corpus, cls.components)
        cls.prepared = bytes(prepared)
        cls.cache_candidate, cls.cache_writes = cache_home_overlay(cls.image, cls.image, cls.link)

    def test_nested_owner_and_before_guards_reject_changed_inputs(self):
        for offset in (0x3ad808, 0x21fc, 0x1179c, 0x2264, 0xc5dac, VARARGS_STUB, VARARGS_STUB+10):
            changed = bytearray(self.prepared)
            changed[offset] ^= 1
            with self.assertRaises(ValueError, msg=hex(offset)):
                compact_overlay(bytes(changed), self.image, self.link, self.corpus, self.components)
        with self.assertRaises(ValueError):
            compact_overlay(self.prepared+b'\0', self.image, self.link, self.corpus, self.components)

    def test_cli_rejects_inherited_full_text_pointer_change_before_output(self):
        from halfspace_compact import main
        changed = bytearray(self.prepared)
        changed[0x1054c] ^= 1
        fake = ROOT / '__invalid_full_text_pointer.gba'
        original_read = Path.read_bytes
        def read(path):
            return bytes(changed) if path == fake else original_read(path)
        with TemporaryDirectory() as temp:
            output = Path(temp) / 'rejected'
            with patch.object(sys, 'argv', ['halfspace_compact', '--input', str(fake), '--out', str(output)]), patch.object(Path, 'read_bytes', read):
                with self.assertRaisesRegex(ValueError, 'Original pointer'):
                    main()
            self.assertFalse(output.exists())

    def test_cache_home_all512_rom_ids_and_second_call_reload(self):
        cache = self.segments['tile_cache']
        self.assertEqual(self.candidate[cache['new']:cache['end']], self.image[cache['new']:cache['end']])
        self.assertEqual(self.candidate[0x1dbc:0x1df0], self.prepared[0x1dbc:0x1df0])
        font = 0x08000000 + self.segments['clear_font']['new']
        for image in (self.image, self.cache_candidate):
            cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
            cpu.mem_map(0x08000000, 0x800000)
            cpu.mem_map(0x02000000, 0x40000)
            cpu.mem_write(0x08000000, image)
            for index in range(512):
                cpu.reg_write(UC_ARM_REG_R4, font + index*32)
                cpu.reg_write(UC_ARM_REG_R1, 0x12345678)
                cpu.reg_write(UC_ARM_REG_R2, 0)
                cpu.reg_write(UC_ARM_REG_LR, 0x02020001)
                cpu.emu_start(0x080c5dad, 0x02020000, count=40)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R6), (index ^ (index >> 6)) & 63)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R1), 0x12345678)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R4), font + index*32)
            if image == self.cache_candidate:
                word = 0xf00fff0f
                cpu.mem_write(0x0200100c, struct.pack('<I', word))
                for profile in (0, 11):
                    for entry, initial_word in ((0x080c5dac, word), (0x080c5e22, 0)):
                        cpu.reg_write(UC_ARM_REG_R4, 0x02001000)
                        cpu.reg_write(UC_ARM_REG_R1, initial_word)
                        cpu.reg_write(UC_ARM_REG_R2, profile)
                        cpu.reg_write(UC_ARM_REG_LR, 0x02020001)
                        cpu.emu_start(entry | 1, 0x02020000, count=40)
                        self.assertEqual(cpu.reg_read(UC_ARM_REG_R6), (word ^ (word >> 5)) >> 26)
                        self.assertEqual(cpu.reg_read(UC_ARM_REG_R1), word)

    def test_cache_collision_full_profile_and_palette_change_lifetime(self):
        def glyph(index):
            tile = bytearray((15 if index >> (2*n % 7) & 1 else 0) |
                             (240 if index >> ((2*n+1) % 7) & 1 else 0) for n in range(32))
            tile[12:16] = bytes(4)  # Every tile deliberately has the same home hash.
            return bytes(tile)
        for clear in (0, 11):
            transform = lambda t: bytes(b | 0xbb for b in t) if clear else t
            for battle, capacity in ((False, 72), (True, 64)):
                tiles = [transform(glyph(i)) for i in range(1, capacity+2)]
                report = cache_cpu(self.candidate, self.segments, tiles, clear=clear, battle=battle)
                self.assertEqual((report['status'], report['inserted']), ('EXHAUSTED', capacity))
                report = cache_cpu(self.candidate, self.segments, tiles[32:], clear=clear, battle=battle, displayed=tiles[:32])
                self.assertEqual((report['status'], report['inserted']), ('EXHAUSTED', capacity-32))
        old = [glyph(i) for i in range(1, 31)]
        solid = [bytes(b | 0xbb for b in glyph(i)) for i in range(31, 61)]
        self.assertEqual(cache_cpu(self.candidate, self.segments, solid, clear=11, battle=True, displayed=old, display_clear=0)['status'], 'PASS')
        self.assertEqual(cache_cpu(self.candidate, self.segments, [bytes(32)], clear=2)['status'], 'EXHAUSTED')

    def test_native_compositor_actual_item_monster_pixels_and_guards(self):
        rows = list(compact_rows(self.image, self.corpus, self.link, self.components))
        for prefix in ('ITEM_001:', 'MONSTER_001:'):
            row, tokens = next((r, t) for r, t in rows if r['binding_id'].startswith(prefix))
            for clear in (0, 11):
                for width in (14, 4):
                    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
                    for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000),
                                     (0x03000000, 0x8000), (0x06000000, 0x20000)):
                        cpu.mem_map(at, size)
                    cpu.mem_write(0x08000000, self.candidate)
                    cpu.mem_write(0x0300004c, struct.pack('<III', 0x0600f800, 0x0600c000, 0))
                    cpu.mem_write(0x0300145a, bytes([clear]))
                    cpu.mem_write(0x03000010, struct.pack('<H', 0x100))
                    cpu.mem_write(0x03000058, b'\x07\0' * 640)
                    cpu.mem_write(0x02001000, b''.join(tokens) + b'\0')
                    cpu.mem_write(0x02000100, bytes((2, 1, width+2, 19, 2, 1, 1, 13)))
                    saved = {r: 0x12340000+r for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11)}
                    for r, v in saved.items(): cpu.reg_write(r, v)
                    for r, v in ((UC_ARM_REG_R0, 0x02000100), (UC_ARM_REG_R1, 0x02001000),
                                 (UC_ARM_REG_R2, clear), (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, 0x02020001)):
                        cpu.reg_write(r, v)
                    cpu.emu_start(0x08000001 + DRAW, 0x02020000, count=100000)
                    self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x02020000)
                    self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
                    for r, v in saved.items(): self.assertEqual(cpu.reg_read(r), v)
                    expected, pixels, _ = compose(resolved_hangul(tokens, self.image, self.segments, clear), proposed_advances(row, tokens), clear)
                    if width == 14:
                        actual = []
                        for n in range(len(expected)):
                            tile = struct.unpack('<H', bytes(cpu.mem_read(0x03000058 + (32+2+n)*2, 2)))[0] & 1023
                            actual.append(bytes(cpu.mem_read(0x0600c000 + tile*32, 32)))
                        self.assertEqual(actual, expected, (prefix, clear))
                        self.assertEqual(cpu.mem_read(0x02000104, 1)[0], 2 + (pixels+7)//8)
                    # Entire left/right guard columns survive narrow-word wrap.
                    for y in range(20):
                        for x in (0, 1, width+2, 31):
                            self.assertEqual(bytes(cpu.mem_read(0x03000058 + (y*32+x)*2, 2)), b'\x07\0')

    def test_empty_repaired_simple_restores_scratch_and_stack(self):
        candidate, _ = repair_simple_trampoline(self.image, self.link)
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000), (0x03000000, 0x8000)):
            cpu.mem_map(at, size)
        cpu.mem_write(0x08000000, candidate)
        saved = {r: 0x12340000+r for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7)}
        for r, v in saved.items(): cpu.reg_write(r, v)
        for r, v in ((UC_ARM_REG_R0, 2), (UC_ARM_REG_R1, 1), (UC_ARM_REG_R2, 0x02001000),
                     (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, 0x02020001)):
            cpu.reg_write(r, v)
        cpu.emu_start(0x08000001 + self.segments['simple_trampoline']['new'], 0x02020000, count=100)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x02020000)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
        for r, v in saved.items(): self.assertEqual(cpu.reg_read(r), v)

    def test_dispatch_unknown_source_caller_mode_and_cursor_use_native_fallback(self):
        row, tokens = next((r, t) for r, t in compact_rows(self.image, self.corpus, self.link, self.components)
                           if r['binding_id'].startswith('JOB_135:'))
        source = 0x08000000 + int(row['current_start'], 16)
        for unknown, caller, mode, cursor in ((False, 0x02020001, 1, 2),
                                              (False, 0x0800fed5, 0, 2),
                                              (False, 0x0800fed5, 2, 2),
                                              (False, 0x0800fed5, 1, 3),
                                              (True, 0x0800fed5, 1, 2)):
            snapshots = []
            for image in (self.image, self.candidate):
                cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
                for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000),
                                 (0x03000000, 0x8000), (0x06000000, 0x20000)):
                    cpu.mem_map(at, size)
                cpu.mem_write(0x08000000, image)
                cpu.mem_write(0x0300004c, struct.pack('<III', 0x0600f800, 0x0600c000, 0))
                cpu.mem_write(0x03000010, struct.pack('<H', 0x100))
                cpu.mem_write(0x02000100, bytes((2, 1, 16, 19, cursor, 2, mode, 13)))
                cpu.mem_write(0x02001000, b''.join(tokens) + b'\0')
                for r, v in ((UC_ARM_REG_R0, 0x02000100),
                             (UC_ARM_REG_R1, 0x02001000 if unknown else source),
                             (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, caller)):
                    cpu.reg_write(r, v)
                cpu.emu_start(0x08001ddd, caller & ~1, count=200000)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), caller & ~1)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
                snapshots.append((bytes(cpu.mem_read(0x03000058, 1280)), bytes(cpu.mem_read(0x02000100, 8))))
            self.assertEqual(snapshots[0], snapshots[1], (unknown, caller, mode, cursor))

    def test_all_resolved_registered_labels_and_callers_preserve_exact_pixels(self):
        samples = dict((r['binding_id'].split(':')[0], (r, t)) for r, t in
                       compact_rows(self.image, self.corpus, self.link, self.components))
        cases = []
        resolved = 0
        for key, (row, tokens) in samples.items():
            callers = next((v for k, v in CALLERS.items() if key.startswith(k)), [])
            if not callers or any(t != b' ' and not (len(t) == 3 and t[0] == 127) for t in tokens): continue
            resolved += 1
            for address in callers:
                caller = int(address, 16)
                offset = 4 if caller == 0x08019155 else 1 if key.startswith(('ITEM_', 'ARTE_')) else 0
                cases.append((key, caller, offset))
        self.assertEqual(resolved, 749)
        for key, caller, offset in cases:
            row, tokens = samples[key]
            for clear in (0, 11):
                cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
                for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000),
                                 (0x03000000, 0x8000), (0x06000000, 0x20000),
                                 (0x0a000000, 0x800000), (0x0c000000, 0x800000)):
                    cpu.mem_map(at, size)
                cpu.mem_write(0x08000000, self.candidate)
                cpu.mem_write(0x0a000000, self.candidate)
                cpu.mem_write(0x0c000000, self.candidate)
                cpu.mem_write(0x0300004c, struct.pack('<III', 0x0600f800, 0x0600c000, 0))
                cpu.mem_write(0x03000010, struct.pack('<H', 0x100))
                cpu.mem_write(0x0300145a, bytes([clear]))
                cpu.mem_write(0x0600c200, bytes([clear*17])*32)
                self.batch_profile(cpu)
                cpu.mem_write(0x02000100, bytes((2, 1, 16, 19, 2+offset, 2, 1, 13)))
                cpu.mem_write(0x02003000, bytes([int(key.split('_')[1])]))
                saved_r4 = (0x02003000 if key.startswith('JOB') else int(key.split('_')[1])
                            if key.startswith('ARTE') else 0x08000000+int(row['pointer_storage'], 16))
                cpu.reg_write(UC_ARM_REG_R4, saved_r4)
                cpu.reg_write(UC_ARM_REG_R6, int(key.split('_')[1]))
                source = 0x08000000+int(row['current_start'], 16)
                if key.startswith('ARTE'):
                    cpu.reg_write(UC_ARM_REG_R0, int(key.split('_')[1]))
                    cpu.reg_write(UC_ARM_REG_R1, 0)
                    cpu.reg_write(UC_ARM_REG_SP, 0x03007e00)
                    cpu.reg_write(UC_ARM_REG_LR, 0x02020101)
                    cpu.emu_start(0x08008c55, 0x02020100, count=10000)
                    source = cpu.reg_read(UC_ARM_REG_R0)
                for r, v in ((UC_ARM_REG_R0, 0x02000100), (UC_ARM_REG_R1, 0x08000000+int(row['current_start'], 16)),
                             (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, caller)):
                    cpu.reg_write(r, v)
                cpu.reg_write(UC_ARM_REG_R1, source)
                cpu.emu_start((caller-4) | 1, caller & ~1, count=200000)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), caller & ~1)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R4), saved_r4)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R6), int(key.split('_')[1]))
                self.assertTrue(cpu.reg_read(UC_ARM_REG_CPSR) & 32)
                glyphs = resolved_hangul(tokens, self.image, self.segments, clear)
                widths = proposed_advances(row, tokens)
                expected, _, _ = compose(glyphs, widths, clear)
                for n, pixels in enumerate(expected):
                    tile = struct.unpack('<H', bytes(cpu.mem_read(0x03000058 + (64+2+offset+n)*2, 2)))[0] & 1023
                    self.assertEqual(bytes(cpu.mem_read(0x0600c000+tile*32, 32)), pixels, (key, caller, clear, n))

    def test_arte_mirror_gate_rejects_nonrom_and_invalid_waitstate_banks(self):
        row = next(r for r in self.corpus['rows'] if r['binding_id'].startswith('ARTE_158:'))
        offset = int(row['current_start'], 16)
        for bank in (0x02000000, 0x03000000, 0x06000000, 0x0e000000):
            cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
            for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000), (0x03000000, 0x8000)):
                cpu.mem_map(at, size)
            cpu.mem_write(0x08000000, self.candidate)
            cpu.mem_write(0x02000100, bytes((2, 1, 16, 19, 3, 2, 1, 13)))
            for r, v in ((UC_ARM_REG_R0, 0x02000100), (UC_ARM_REG_R1, bank+offset),
                         (UC_ARM_REG_R4, 158), (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, 0x080140f5)):
                cpu.reg_write(r, v)
            def stop_before_formatter(c, at, size, _):
                if at == 0x08002648: c.emu_stop()
            cpu.hook_add(UC_HOOK_CODE, stop_before_formatter)
            cpu.emu_start(0x08000001+VARARGS_STUB, 0x080140f4, count=1000)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x08002648)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R6), 0)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R1), bank+offset)

    def test_every_item_status_icon_retains_native_pixels_and_column_alignment(self):
        rows = [(r, t) for r, t in compact_rows(self.image, self.corpus, self.link, self.components)
                if r['binding_id'].startswith('ITEM_') and self.image[int(r['pointer_storage'], 16)+6] & 8]
        self.assertEqual((len(rows), sum(b' ' in t for _, t in rows)), (62, 35))
        for row, tokens in rows:
            item = int(row['binding_id'].split(':')[0].split('_')[1])
            for clear in (0, 11):
                snapshots = []
                for image in (self.image, self.candidate):
                    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
                    for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000),
                                     (0x03000000, 0x8000), (0x06000000, 0x20000)):
                        cpu.mem_map(at, size)
                    cpu.mem_write(0x08000000, image)
                    cpu.mem_write(0x0300004c, struct.pack('<III', 0x0600f800, 0x0600c000, 0))
                    cpu.mem_write(0x03000010, struct.pack('<H', 0x100))
                    cpu.mem_write(0x0300145a, bytes([clear]))
                    cpu.mem_write(0x0600c200, bytes([clear*17])*32)
                    cpu.mem_write(0x02000100, bytes((2, 1, 30, 19, 3, 2, 1, 13)))
                    for reg, value in ((UC_ARM_REG_R4, 0x08000000+int(row['pointer_storage'], 16)),
                                       (UC_ARM_REG_R5, 0x02000100), (UC_ARM_REG_R6, item),
                                       (UC_ARM_REG_SP, 0x03007e00)):
                        cpu.reg_write(reg, value)
                    cursors = []
                    def label_return(c, at, size, _):
                        if at == 0x080117a4: cursors.append(c.mem_read(0x02000104, 1)[0])
                    cpu.hook_add(UC_HOOK_CODE, label_return)
                    # Execute both actual callback BLs: native label, then %5g icon.
                    cpu.emu_start(0x0801179d, 0x080117b6, count=200000)
                    self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x080117b6)
                    self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
                    label_end = cursors[0]
                    tile = struct.unpack('<H', cpu.mem_read(0x03000058+(64+label_end)*2, 2))[0]
                    icon = bytes(cpu.mem_read(0x0600c000+(tile & 1023)*32, 32))
                    snapshots.append((label_end, cpu.mem_read(0x02000104, 1)[0], tile, icon))
                    if image == self.candidate:
                        expected, width, _ = compose(resolved_hangul(tokens, self.image, self.segments, clear), proposed_advances(row, tokens), clear)
                        self.assertEqual(label_end, 3+(width+7)//8, row['binding_id'])
                        self.assertIn((label_end-3)*8-width, (0, 4))
                        for n, pixels in enumerate(expected):
                            actual = struct.unpack('<H', cpu.mem_read(0x03000058+(64+3+n)*2, 2))[0] & 1023
                            self.assertEqual(bytes(cpu.mem_read(0x0600c000+actual*32, 32)), pixels, (row['binding_id'], clear, n))
                self.assertEqual(snapshots[0][2:], snapshots[1][2:], row['binding_id'])
                self.assertEqual(snapshots[1][1]-snapshots[1][0], 1, row['binding_id'])

    def test_native_icon_template_keeps_pixels_descriptor_and_abi(self):
        for clear in (0, 11):
            for mode in (0, 1, 2):
                snapshots = []
                for image in (self.image, self.candidate):
                    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
                    for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000),
                                     (0x03000000, 0x8000), (0x06000000, 0x20000)):
                        cpu.mem_map(at, size)
                    cpu.mem_write(0x08000000, image)
                    cpu.mem_write(0x0300004c, struct.pack('<III', 0x0600f800, 0x0600c000, 0))
                    cpu.mem_write(0x03000010, struct.pack('<H', 0x100))
                    cpu.mem_write(0x0300145a, bytes([clear]))
                    cpu.mem_write(0x02000100, bytes((2, 1, 30, 19, 3, 2, mode, 13)))
                    saved = {r: 0x12340000+r for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7)}
                    for r, v in saved.items(): cpu.reg_write(r, v)
                    for r, v in ((UC_ARM_REG_R0, 0x02000100), (UC_ARM_REG_R1, 0x082c39c4),
                                 (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, 0x02020001)):
                        cpu.reg_write(r, v)
                    cpu.emu_start(0x08001ddd, 0x02020000, count=100000)
                    self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x02020000)
                    self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
                    for r, v in saved.items(): self.assertEqual(cpu.reg_read(r), v)
                    snapshots.append((bytes(cpu.mem_read(0x03000058, 1280)), bytes(cpu.mem_read(0x0600c000, 0x3800)), bytes(cpu.mem_read(0x02000100, 8))))
                self.assertEqual(snapshots[0], snapshots[1], (clear, mode))

    def test_generic_variadic_entry_still_returns_to_arm(self):
        for image in (self.image, self.candidate):
            cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
            for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000), (0x03000000, 0x8000)):
                cpu.mem_map(at, size)
            cpu.mem_write(0x08000000, image)
            cpu.mem_write(0x02000100, bytes((2, 1, 30, 19, 3, 2, 1, 13)))
            saved = {r: 0x12340000+r for r in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7)}
            for r, v in saved.items(): cpu.reg_write(r, v)
            for r, v in ((UC_ARM_REG_R0, 0x02000100), (UC_ARM_REG_R1, 0x02001000),
                         (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, 0x02020000)):
                cpu.reg_write(r, v)
            cpu.emu_start(0x08001ddd, 0x02020000, count=10000)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x02020000)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
            self.assertFalse(cpu.reg_read(UC_ARM_REG_CPSR) & 32)
            for r, v in saved.items(): self.assertEqual(cpu.reg_read(r), v)

    def test_private_dispatch_rejects_wrong_stub_lr_and_outer_caller(self):
        row = next(r for r in self.corpus['rows'] if r['binding_id'].startswith('ITEM_002:'))
        for stub_lr, outer in ((0x08001de9, 0x080117a5), (0x02020001, 0x080117a5),
                               (0x080cab55, 0x02020101)):
            cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
            for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000), (0x03000000, 0x8000)):
                cpu.mem_map(at, size)
            cpu.mem_write(0x08000000, self.candidate)
            cpu.mem_write(0x02000100, bytes((2, 1, 30, 19, 3, 2, 1, 13)))
            source = 0x08000000+int(row['current_start'], 16)
            cpu.mem_write(0x03007df0, struct.pack('<IIII', source, 0, 0, outer))
            for r, v in ((UC_ARM_REG_R0, 0x02000100), (UC_ARM_REG_R1, source),
                         (UC_ARM_REG_R2, 0x03007df0), (UC_ARM_REG_R6, 2),
                         (UC_ARM_REG_SP, 0x03007df0), (UC_ARM_REG_LR, stub_lr)):
                cpu.reg_write(r, v)
            def before_formatter(c, at, size, _):
                if at == 0x08002648: c.emu_stop()
            cpu.hook_add(UC_HOOK_CODE, before_formatter)
            cpu.emu_start(0x08001439, 0x02020000, count=1000)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x08002648)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R6), 0)

    def batch_cpu(self, *, clear=0, battle=False):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000),
                         (0x03000000, 0x8000), (0x06000000, 0x20000)):
            cpu.mem_map(at, size)
        cpu.mem_write(0x08000000, self.candidate)
        cpu.mem_write(0x0300004c, struct.pack('<III', 0x0600f800, 0x0600c000, 0))
        cpu.mem_write(0x03000010, struct.pack('<H', 0x100 | int(battle)))
        cpu.mem_write(0x0300145a, bytes([clear]))
        self.batch_profile(cpu)
        cpu.reg_write(UC_ARM_REG_R8, 0x02000100)
        cpu.reg_write(UC_ARM_REG_SP, 0x03007e00)
        return cpu

    def batch_call(self, cpu, name, argument=0):
        cpu.reg_write(UC_ARM_REG_R0, argument)
        cpu.reg_write(UC_ARM_REG_LR, 0x02020001)
        cpu.emu_start(0x08000001+BATCH_OWNERS[name][0], 0x02020000, count=100000)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x02020000)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
        return cpu.reg_read(UC_ARM_REG_R0)

    def test_enabled_batch_capacity_both_maps_and_conservative_refresh(self):
        for clear in (0, 11):
            for battle, capacity in ((False, 72), (True, 64)):
                cpu = self.batch_cpu(clear=clear, battle=battle)
                self.batch_call(cpu, 'init')
                self.assertEqual(bytes(cpu.mem_read(0x0200010c, 4)), bytes(4))
                original = []
                for index in range(capacity):
                    tile = bytes([index+1])*32
                    if clear: tile = bytes(v | 0xbb for v in tile[:1])+tile[1:]
                    cpu.mem_write(0x02001000, tile)
                    slot = self.batch_call(cpu, 'lookup', 0x02001000)
                    self.assertLess(slot, 512)
                    cpu.mem_write(0x03000058+index*2, struct.pack('<H', slot))
                    original.append((slot, tile))
                cpu.mem_write(0x02001000, b'\xfe'*32)
                self.assertEqual(self.batch_call(cpu, 'lookup', 0x02001000), 0xffffffff)
                for slot, tile in original:
                    self.assertEqual(bytes(cpu.mem_read(0x0600c000+slot*32, 32)), tile)
                # Replacing an own shadow reference can leave a conservative bit;
                # a full cached set must refresh actual maps rather than fail.
                cpu.mem_write(0x03000058, struct.pack('<H', original[1][0]))
                # The old displayed reference still pins the first slot.
                cpu.mem_write(0x0600f800, struct.pack('<H', original[0][0]))
                self.batch_call(cpu, 'init')
                self.assertEqual(self.batch_call(cpu, 'lookup', 0x02001000), 0xffffffff)
                cpu.mem_write(0x0600f800, bytes(2))
                slot = self.batch_call(cpu, 'lookup', 0x02001000)
                self.assertEqual(slot, original[0][0])
                for old, tile in original[1:]:
                    self.assertEqual(bytes(cpu.mem_read(0x0600c000+old*32, 32)), tile)

    def test_batch_init_rejects_unproved_irq_dma_and_sound_profiles(self):
        changes = [(0x04000200, b'\x03\x20'), (0x03007ffc, bytes(4)),
                   (0x03002b04, bytes(4)), (0x03007ff0, bytes(4)),
                   (0x02003f00, bytes(4)), (0x040000ba, b'\x00\x80'),
                   (0x040000de, b'\x00\x80'), (0x040000c6, b'\x00\x84'),
                   (0x040000d2, b'\x00\x84')]
        for at, data in changes:
            cpu = self.batch_cpu()
            cpu.mem_write(at, data)
            self.batch_call(cpu, 'init')
            self.assertEqual(bytes(cpu.mem_read(0x0200010c, 4)), b'\xff'*4, hex(at))
            cpu.mem_write(0x02001000, b'\xff'*32)
            self.assertNotEqual(self.batch_call(cpu, 'lookup', 0x02001000), 0xffffffff)

    def test_batch_wrap_resets_after_xy_change_and_actual_scroll(self):
        for scroll in (False, True):
            snapshots = []
            for private in (False, True):
                cpu = self.batch_cpu()
                cpu.mem_write(0x02000100, struct.pack('<5I', 0, 0, 0, 376, 72))
                y = 18 if scroll else 2
                cpu.mem_write(0x02000400, bytes((2, 1, 6, 19, 6, y, 1, 13)))
                cpu.mem_write(0x03000058, b'\x78\x01'*640)
                if private:
                    self.batch_call(cpu, 'wrap', 0x02000400)
                    self.assertEqual(bytes(cpu.mem_read(0x0200010c, 4)), bytes(4))
                else:
                    cpu.reg_write(UC_ARM_REG_R0, 0x02000400)
                    cpu.reg_write(UC_ARM_REG_LR, 0x02020001)
                    cpu.emu_start(0x08001a81, 0x02020000, count=100000)
                snapshots.append((bytes(cpu.mem_read(0x02000400, 8)), bytes(cpu.mem_read(0x03000058, 1280))))
            self.assertEqual(snapshots[0], snapshots[1], scroll)
        cpu = self.batch_cpu()
        cpu.mem_write(0x02000100, struct.pack('<5I', 1, 2, 3, 376, 72))
        cpu.mem_write(0x02000400, bytes((2, 1, 6, 19, 3, 2, 1, 13)))
        self.batch_call(cpu, 'wrap', 0x02000400)
        self.assertEqual(bytes(cpu.mem_read(0x02000100, 20)), struct.pack('<5I', 1, 2, 3, 376, 72))

    def test_every_known_family_rejects_ram_saved_and_mismatched_sources(self):
        samples = {r['binding_id'].split(':')[0]: r for r in self.corpus['rows']}
        for key, caller in (('JOB_135', 0x0800fed5), ('ITEM_002', 0x080117a5),
                            ('ARTE_158', 0x080140f5), ('MONSTER_001', 0x08019155),
                            ('MONSTER_001', 0x0800f54b)):
            row = samples[key]
            ident = int(key.split('_')[1])
            valid = 0x08000000+int(row['current_start'], 16)
            for source in (0x02001000, 0x03001000, 0x0e001000, valid+4):
                cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
                for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000), (0x03000000, 0x8000)):
                    cpu.mem_map(at, size)
                cpu.mem_write(0x08000000, self.candidate)
                cpu.mem_write(0x02000100, bytes((2, 1, 30, 19, 3, 2, 1, 13)))
                cpu.mem_write(0x02003000, struct.pack('<I', source) if key.startswith('MONSTER') else bytes([ident]))
                caller_r4 = 0x02003000 if key.startswith(('JOB', 'MONSTER')) else ident
                if key.startswith('MONSTER') and source == valid+4:
                    caller_r4 = 0x08000000+int(row['pointer_storage'], 16)
                for reg, value in ((UC_ARM_REG_R0, 0x02000100), (UC_ARM_REG_R1, source),
                                   (UC_ARM_REG_R4, caller_r4),
                                   (UC_ARM_REG_R6, ident), (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, caller)):
                    cpu.reg_write(reg, value)
                def before_formatter(c, at, size, _):
                    if at == 0x08002648: c.emu_stop()
                cpu.hook_add(UC_HOOK_CODE, before_formatter)
                cpu.emu_start(0x08000001+VARARGS_STUB, caller & ~1, count=1000)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x08002648)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R6), 0, (key, hex(source)))
                self.assertEqual(cpu.reg_read(UC_ARM_REG_R1), source)

    def test_actual_encoded_item_monster_native_consumer_unchanged(self):
        samples = dict((row['binding_id'], (row, tokens)) for row, tokens in
                       compact_rows(self.image, self.corpus, self.link, self.components))
        for prefix in ('ITEM_001:', 'MONSTER_001:'):
            binding = next(k for k in samples if k.startswith(prefix))
            row, tokens = samples[binding]
            for clear in (0, 11):
                for simple in (False, True):
                    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
                    for at, size in ((0x08000000, 0x800000), (0x02000000, 0x40000),
                                     (0x03000000, 0x8000), (0x06000000, 0x20000)):
                        cpu.mem_map(at, size)
                    candidate = repair_simple_trampoline(self.image, self.link)[0] if simple else self.image
                    cpu.mem_write(0x08000000, candidate)
                    cpu.mem_write(0x0300004c, struct.pack('<III', 0x0600f800, 0x0600c000, 0))
                    cpu.mem_write(0x0300145a, bytes([clear]))
                    cpu.mem_write(0x03000010, struct.pack('<H', 0x100))
                    cpu.reg_write(UC_ARM_REG_SP, 0x03007e00)
                    cpu.reg_write(UC_ARM_REG_LR, 0x02020001)
                    pointer = 0x08000000 + int(row['current_start'], 16)
                    if simple:
                        cpu.reg_write(UC_ARM_REG_R0, 0)
                        cpu.reg_write(UC_ARM_REG_R1, 0)
                        cpu.reg_write(UC_ARM_REG_R2, pointer)
                    else:
                        cpu.mem_write(0x02000100, bytes((0, 0, 30, 20, 0, 0, 0, 15, 0, 0, 0, 0)))
                        cpu.reg_write(UC_ARM_REG_R0, 0x02000100)
                        cpu.reg_write(UC_ARM_REG_R1, pointer)
                    entry = 0x08001df0 if simple else 0x08001ac8
                    cpu.emu_start(entry | 1, 0x02020000, count=100000)
                    self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x02020000, binding)
                    self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
                    glyphs = resolved_hangul(tokens, self.image, self.segments, clear)
                    for n, (token, glyph) in enumerate(zip(tokens, glyphs)):
                        tile = struct.unpack('<H', bytes(cpu.mem_read(0x03000058 + n*2, 2)))[0] & 1023
                        if token == b' ':
                            self.assertEqual(tile, 0x10)
                        else:
                            self.assertEqual(bytes(cpu.mem_read(0x0600c000 + tile*32, 32)), glyph, (binding, clear, simple, n, tile))
                    if not simple:
                        self.assertEqual(cpu.mem_read(0x02000104, 1)[0], len(tokens))


class NormalCompactComponentTests(unittest.TestCase):
    # These components execute in isolated CPU memory; no new ROM owner is used.
    @classmethod
    def setUpClass(cls):
        CurrentROMConsumerTests.setUpClass.__func__(cls)

    def normal_components(self):
        from halfspace_compact import KEYBOARD
        from halfspace_compact import normal_marker_sources
        from halfspace_compact_consumers import NUMERIC_COLUMNS
        names = ('draw', 'loop', 'glyph', 'emit', 'flush', 'space', 'control', 'wrap', 'store', 'validate',
                 'prepare', 'has_format', 'render_gate', 'small', 'simple', 'simple_finish',
                 'format', 'format_finish', 'format_prepare', 'format_has_string', 'argument',
                 'copy_argument', 'native_format', 'format_leave', 'prompt', 'format_gate', 'label_draw', 'plain_label')
        values = {'NORMAL_'+name.upper(): 0x08070000+n*0x100 for n, name in enumerate(names)}
        exclusions = {0x082b95bc, 0x082bd510, 0x082c7810, 0x082c78b8}
        exclusions |= {int(row['original_start'], 16)+0x08000000 for row, _ in
                       compact_rows(self.image, self.corpus, self.link, self.components) if row['binding_id'] in KEYBOARD}
        values.update(BATCH_INIT=0x08000000+BATCH_OWNERS['init'][0],
                      BATCH_LOOKUP=0x08000000+BATCH_OWNERS['lookup'][0],
                      BATCH_WRAP=0x08000000+BATCH_OWNERS['wrap'][0],
                      SOURCE_GATE=0x08078000, COMPACT_SOURCE_LOOKUP=0x08078100,
                      NUMERIC_COPY=0x08078200, MARK_COPY=0x08078300,
                      NORMAL_PAIR=0x08078400, SOURCE_EXCLUSIONS=0x08078500,
                      NUMERIC_POLICY=0x08078600, SOURCE_EXCLUSION_COUNT=len(exclusions),
                      MARK_LOOP=0x08078701,
                      COMPACT_FONT=0x08000000+self.segments['clear_font']['new'],
                      DIAGNOSTIC_STOP=0x080b9de4)
        writes = []
        sources = [(0x70000+n*0x100, 'normal_'+name) for n, name in enumerate(names)]
        sources += [(0x78000, 'source_gate'), (0x78100, 'source_lookup'),
                    (0x78200, 'numeric_policy'), (0x78300, 'marker_validate'),
                    (0x78400, 'pair'), (0x78700, 'marker_loop')]
        split_marker = normal_marker_sources()
        for offset, name in sources:
            source = (split_marker[name] if name in split_marker else
                      (ROOT/('asm/halfspace_compact_'+name+'.s')).read_text(encoding='utf-8'))
            for key, value in sorted(values.items(), key=lambda item: -len(item[0])):
                source = source.replace(key, hex(value))
            code = assemble(source, offset)
            self.assertLessEqual(len(code), 126, name)
            writes.append((0x08000000+offset, code))
        writes.append((values['SOURCE_EXCLUSIONS'], b''.join(struct.pack('<I', item) for item in sorted(exclusions))))
        writes.append((values['NUMERIC_POLICY'], b''.join(struct.pack('<IBBxx', *item) for item in NUMERIC_COLUMNS.values())))
        return values, writes

    def test_numeric_fast_gate_exact_identity_and_untouched_call_frame(self):
        values,writes=self.normal_components()
        prepared=getattr(self,'normal_report',{'symbols':values})['symbols']['NORMAL_FORMAT']
        native=(0x082c49a4,0x082c49a8,0x082c49ac,0x082c4c64,0x082c4c68,0x082c4c6c,
                0x082c3e40,0x082c3e48,0x082c3e50)
        for source in native+(0x082c49a5,0x082c49a0,
                       0x082c49b0,0x082c1da0,0x082c1da4,0x02001000,0x082b566c):
            cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
            cpu.mem_map(0x08000000,0x800000)
            cpu.mem_map(0x03000000,0x8000)
            cpu.mem_write(0x08000000,self.candidate)
            for at,code in writes:cpu.mem_write(at,code)
            registers={UC_ARM_REG_R0:0x02000100,UC_ARM_REG_R1:source,UC_ARM_REG_R2:0x02002000,
                       UC_ARM_REG_R4:0x44444444,UC_ARM_REG_R7:0x77777777,
                       UC_ARM_REG_SP:0x03007e00,UC_ARM_REG_LR:0x02020001}
            for reg,value in registers.items():cpu.reg_write(reg,value)
            targets=[]
            def stop(uc,address,size,data):
                if address in (prepared,values['NORMAL_NATIVE_FORMAT']):
                    targets.append(address);uc.emu_stop()
            cpu.hook_add(UC_HOOK_CODE,stop)
            cpu.emu_start(values['NORMAL_FORMAT_GATE']|1,0,count=50)
            self.assertEqual(targets,[values['NORMAL_NATIVE_FORMAT'] if source in
                                     native else prepared])
            for reg,value in registers.items():self.assertEqual(cpu.reg_read(reg),value)

    def test_general_leaf_all_ascii_pixels_halfphase_profiles_and_simple_nowrap(self):
        values, writes = self.normal_components()
        from halfspace_compact import KEYBOARD
        for clear in (0, 11):
            for battle in (False, True):
                for char in range(32, 127):
                    cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
                    for address, size in ((0x08000000, 0x800000), (0x02000000, 0x40000),
                                          (0x03000000, 0x8000), (0x06000000, 0x20000)):
                        cpu.mem_map(address, size)
                    cpu.mem_write(0x08000000, self.candidate)
                    for at, code in writes: cpu.mem_write(at, code)
                    CurrentROMConsumerTests.batch_profile(cpu)
                    cpu.mem_write(0x0300004c, struct.pack('<III', 0x0600f800, 0x0600c000, 0))
                    cpu.mem_write(0x0300145a, bytes([clear]))
                    cpu.mem_write(0x03000010, struct.pack('<H', 1 if battle else 0x100))
                    cpu.mem_write(0x03000058, b'\x07\0'*640)
                    blank = bytes([clear*17])*32
                    ascii_tile = bytes((0xff if (index+char) % 3 else clear*17) for index in range(32))
                    cpu.mem_write(0x0600c000+(char-16)*32, ascii_tile)
                    first, last = resolved_hangul([b'\x7f\x01\x01', b'\x7f\x01\x02'], self.image, self.segments, clear)
                    raw = b'\x7f\x01\x01\x1f'+bytes([char])+b'\x7f\x01\x02\0'
                    cpu.mem_write(0x02001000, raw)
                    # nowrap must preserve native simple-printer overflow across a narrow descriptor.
                    nowrap = int(char % 2 == 0)
                    cpu.mem_write(0x02000100, bytes((2, 1, 3 if nowrap else 20, 19, 2, 1, 0, 13)))
                    saved = {reg: 0x12340000+reg for reg in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                                                          UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11)}
                    for reg, value in saved.items(): cpu.reg_write(reg, value)
                    for reg, value in ((UC_ARM_REG_R0, 0x02000100), (UC_ARM_REG_R1, 0x02001000),
                                       (UC_ARM_REG_R2, clear), (UC_ARM_REG_R3, nowrap),
                                       (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, 0x02020001)):
                        cpu.reg_write(reg, value)
                    cpu.emu_start(values['NORMAL_DRAW'] | 1, 0x02020000, count=100000)
                    self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x02020000)
                    self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
                    for reg, value in saved.items(): self.assertEqual(cpu.reg_read(reg), value)
                    expected, _, _ = compose([first, blank, ascii_tile, last], [8, 4, 8, 8], clear)
                    actual = []
                    for n in range(len(expected)):
                        entry = struct.unpack('<H', bytes(cpu.mem_read(0x03000058+(32+2+n)*2, 2)))[0]
                        self.assertEqual(entry >> 12, 13)
                        actual.append(bytes(cpu.mem_read(0x0600c000+(entry & 1023)*32, 32)))
                    self.assertEqual(actual, expected, (char, clear, battle))
                    self.assertEqual(bytes(cpu.mem_read(0x02001000, len(raw))), raw)
                    self.assertEqual(cpu.mem_read(0x02000104, 1)[0], 2+len(expected))

    def test_plain_label_batch_requires_five_pure_hangul_before_profile_gate(self):
        values, writes = self.normal_components()
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        cpu.mem_map(0x08000000, 0x800000)
        cpu.mem_map(0x02000000, 0x40000)
        cpu.mem_write(0x08000000, self.candidate)
        for address, code in writes: cpu.mem_write(address, code)
        # A rejecting profile gate marks entry without touching graphics memory.
        cpu.mem_write(values['NORMAL_RENDER_GATE'], assemble('movs r0,#0\nbx lr', 0))
        entered = []
        hook = cpu.hook_add(UC_HOOK_CODE, lambda uc, address, size, data: entered.append(address)
                            if address == values['NORMAL_RENDER_GATE'] else None)
        glyph = b'\x7f\x01\x01'
        cases = [(glyph*n+b'\0', n >= 5) for n in (0, 1, 4, 5, 15)]
        cases += [(glyph*5+tail+b'\0', False) for tail in (b'A', b' ', b'\x1f', b'\n', b'%s')]
        for raw, reaches_gate in cases:
            entered.clear()
            cpu.mem_write(0x02001000, raw)
            for reg, value in ((UC_ARM_REG_R0, 0x02000100), (UC_ARM_REG_R1, 0x02001000),
                               (UC_ARM_REG_SP, 0x0203e000), (UC_ARM_REG_LR, 0x02020001)):
                cpu.reg_write(reg, value)
            cpu.emu_start(values['NORMAL_PLAIN_LABEL'] | 1, 0x02020000, count=3000)
            self.assertEqual(bool(entered), reaches_gate, raw)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R0), 0)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x0203e000)
            self.assertEqual(bytes(cpu.mem_read(0x02001000, len(raw))), raw)
        cpu.hook_del(hook)

    def test_general_validator_glyph_boundaries_controls_and_marker_parameters(self):
        values, writes = self.normal_components()
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        cpu.mem_map(0x08000000, 0x800000)
        cpu.mem_map(0x02000000, 0x40000)
        cpu.mem_write(0x08000000, self.candidate)
        for at, code in writes: cpu.mem_write(at, code)
        cases = [(b'A\x1fB\0', 0, True, 1), (b'\x7f\x01\x1f\0', 0, True, 0),
                 (b'\x7f\x11\x10\0', 0, True, 0), (b'\x7f\x11\x11\0', 0, False, 0),
                 (b'\x7f\0\1\0', 0, False, 0), (b'\x7f\1\0', 0, False, 0),
                 (b'A\x0aB\x10C\0', 0, True, 0),
                 (b'A\x11D\0', 0, False, 0),
                 (b'A\x11\0', 0, True, 0), (b'A\x11\0', 1, False, 0),
                 (b'A\x0aB\0', 1, False, 0), (b'A\x10B\0', 1, False, 0),
                 (b'\x12\0', 0, False, 0), (b'\x80\0', 0, False, 0)]
        for raw, simple, valid, count in cases:
            cpu.mem_write(0x02001000, raw)
            for reg, value in ((UC_ARM_REG_R0, 0x02001000), (UC_ARM_REG_R1, len(raw)),
                               (UC_ARM_REG_R2, simple), (UC_ARM_REG_SP, 0x0203e000), (UC_ARM_REG_LR, 0x02020001)):
                cpu.reg_write(reg, value)
            cpu.emu_start(values['NORMAL_VALIDATE'] | 1, 0x02020000, count=3000)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x02020000)
            self.assertEqual(bool(cpu.reg_read(UC_ARM_REG_R0)), valid, raw)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R1), count, raw)
        cpu.mem_map(0xfffff000, 0x1000)
        cpu.mem_map(0, 0x1000)
        cpu.mem_write(0xfffffffc, b'A\x7f\x01\x01')
        cpu.mem_write(0, b'\0')
        for reg, value in ((UC_ARM_REG_R0, 0xfffffffc), (UC_ARM_REG_R1, 3), (UC_ARM_REG_R2, 0),
                           (UC_ARM_REG_SP, 0x0203e000), (UC_ARM_REG_LR, 0x02020001)):
            cpu.reg_write(reg, value)
        cpu.emu_start(values['NORMAL_VALIDATE'] | 1, 0x02020000, count=3000)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_R0), 0)

    def test_direct_wrappers_keep_rom_alias_identity_and_mutable_name_spacing(self):
        from halfspace_compact_consumers import prepared_copy
        from strict_unit_codec import units
        values, writes = self.normal_components()
        rows = compact_rows(self.image, self.corpus, self.link, self.components)
        selected = [item for item in rows if item[0]['binding_id'].startswith(('BATTLE_NAME_033:', 'BATTLE_NAME_036:',
                                                                            'ARTE_158:', 'ARTE_159:'))]
        selected += [next(item for item in rows if item[0]['binding_id'].startswith('ITEM_')
                          and b' ' in item[1] and all(t == b' ' or t[0] == 127 for t in item[1]))]
        for row, tokens in selected:
            raw = b''.join(tokens)+b'\0'
            original = 0x08000000+int(row['original_start'], 16)
            if row['variant_selection'] != 1:
                original += 0x02000000 if row['variant_selection'] == 11 else 0x04000000
            for clear in (0, 11):
                for simple in (False, True):
                    for mutable in (False, True):
                        for arm_return in (False, True):
                            cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
                            for address, size in ((0x08000000, 0x800000), (0x02000000, 0x40000),
                                                  (0x03000000, 0x8000), (0x06000000, 0x20000)):
                                cpu.mem_map(address, size)
                            cpu.mem_write(0x08000000, self.candidate)
                            if original >= 0x0a000000:
                                page = original & ~0xfff
                                cpu.mem_map(page, 0x1000)
                                offset = page & 0x7fffff
                                cpu.mem_write(page, self.candidate[offset:offset+0x1000])
                            for at, code in writes: cpu.mem_write(at, code)
                            CurrentROMConsumerTests.batch_profile(cpu)
                            cpu.mem_write(0x0300004c, struct.pack('<III', 0x0600f800, 0x0600c000, 0))
                            cpu.mem_write(0x0300145a, bytes([clear]))
                            cpu.mem_write(0x03000058, b'\x07\0'*640)
                            blank = bytes([clear*17])*32
                            ascii_tiles = {char: (blank if char == 32 else bytes(
                                0xff if (n+char) % 3 else clear*17 for n in range(32))) for char in range(32, 127)}
                            for char, tile in ascii_tiles.items(): cpu.mem_write(0x0600c000+(char-16)*32, tile)
                            cpu.mem_write(0x02001000, raw)
                            source = 0x02001000 if mutable else original
                            # The actor resolver must retain ROM versus RAM origin, even for equal bytes.
                            if not simple and original < 0x0a000000:
                                cpu.mem_write(0x02002000, b'\x7f\0ND'+struct.pack('<I', source)+b'\0\0')
                                source = 0x02002000
                            cpu.mem_write(0x02000100, bytes((2, 1, 28, 19, 2, 1, 0, 13)))
                            expected_raw = raw if mutable else prepared_copy(row['binding_id'], raw, 0x08000000+int(row['original_start'], 16))
                            expected_tiles, widths = [], []
                            for token in units(expected_raw[:-1], 'compact'):
                                if token == b'\x1f': tile, width = blank, 4
                                elif token[0] == 127:
                                    tile, width = resolved_hangul([token], self.image, self.segments, clear)[0], 8
                                else: tile, width = ascii_tiles[token[0]], 8
                                expected_tiles.append(tile); widths.append(width)
                            expected, _, _ = compose(expected_tiles, widths, clear)
                            saved = {reg: 0x12340000+reg for reg in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                                                                  UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11)}
                            for reg, value in saved.items(): cpu.reg_write(reg, value)
                            args = (2, 1, source) if simple else (0x02000100, source, 0x12345678)
                            for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2), args): cpu.reg_write(reg, value)
                            cpu.reg_write(UC_ARM_REG_R3, 0x24681357)
                            cpu.reg_write(UC_ARM_REG_SP, 0x03007e00)
                            cpu.reg_write(UC_ARM_REG_LR, 0x02020000 if arm_return else 0x02020001)
                            entry = values['NORMAL_SIMPLE' if simple else 'NORMAL_SMALL']
                            try:
                                cpu.emu_start(entry | 1, 0x02020000, count=200000)
                            except Exception as error:
                                self.fail((row['binding_id'], clear, simple, mutable, arm_return,
                                           hex(cpu.reg_read(UC_ARM_REG_PC)), str(error)))
                            self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x02020000)
                            self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
                            self.assertEqual(bool(cpu.reg_read(UC_ARM_REG_CPSR) & 32), not arm_return)
                            for reg, value in saved.items(): self.assertEqual(cpu.reg_read(reg), value)
                            actual = []
                            for n in range(len(expected)):
                                entry = struct.unpack('<H', bytes(cpu.mem_read(0x03000058+(34+n)*2, 2)))[0]
                                self.assertEqual(entry >> 12, 14 if simple else 13)
                                actual.append(bytes(cpu.mem_read(0x0600c000+(entry & 1023)*32, 32)))
                            self.assertEqual(actual, expected, (row['binding_id'], clear, simple, mutable, arm_return))
                            self.assertEqual(bytes(cpu.mem_read(0x02001000, len(raw))), raw)

    def test_formatter_uses_private_buffers_and_preserves_mutable_arguments(self):
        from unicorn import UC_HOOK_CODE
        from halfspace_compact_consumers import prepared_copy, NUMERIC_COLUMNS
        values,writes=self.normal_components()
        rows=compact_rows(self.image,self.corpus,self.link,self.components)
        name=next((r,t) for r,t in rows if r['binding_id'].startswith('BATTLE_NAME_036:'))
        templates=[(r,t) for r,t in rows if r['binding_id'] in NUMERIC_COLUMNS]
        plain_sources={0x2b3f20,0x2b3c8c,0x2b3c54,0x2b3b98,0x2b39ac,
                       0x2b93cc,0x2b93bc,0x2b9200}
        templates += [(r,t) for r,t in rows if int(r['original_start'],16) in plain_sources]
        templates += [({'binding_id':'bare','original_start':'002C1DA0'},[b'%',b's'])]
        for row,tokens in templates:
            for mutable in (False,True):
                cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
                for at,size in ((0x08000000,0x800000),(0x02000000,0x40000),(0x03000000,0x8000)):
                    cpu.mem_map(at,size)
                cpu.mem_write(0x08000000,self.candidate)
                for at,code in writes:cpu.mem_write(at,code)
                cpu.mem_write(0x0300004c,struct.pack('<III',0x0600f800,0x0600c000,0))
                cpu.mem_write(0x02000100,bytes((2,1,28,19,2,1,0,13)))
                source=0x08000000+int(row['original_start'],16)
                is_name=row['binding_id']=='bare'
                raw=b''.join(tokens)+b'\0'
                name_raw=b''.join(name[1])+b'\0'
                cpu.mem_write(0x02001000,name_raw)
                arg=(0x02001000 if mutable else 0x08000000+int(name[0]['original_start'],16)) if is_name else 42
                cpu.mem_write(0x02002000,struct.pack('<4I',source,arg,17,23))
                seen=[]
                formatter_calls=[]
                def text_at(address):
                    b=bytes(cpu.mem_read(address,160));return b[:b.index(0)+1]
                def hook(uc,address,size,data):
                    if address==0x08002648:formatter_calls.append(address)
                    if address in (values['NORMAL_DRAW'],0x080c5a3c,0x08002264):
                        text=text_at(uc.reg_read(UC_ARM_REG_R1))
                        if address==0x08002264:
                            # Fused renderer consumes lexical spaces as native20.
                            text=text.replace(b' ',b'\x1f')
                        seen.append((address,text))
                        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
                    elif address==values['NORMAL_NATIVE_FORMAT']:
                        self.fail('Unexpected native fallback '+row['binding_id'])
                handle=cpu.hook_add(UC_HOOK_CODE,hook)
                for reg,value in ((UC_ARM_REG_R0,0x02000100),(UC_ARM_REG_R1,source),(UC_ARM_REG_R2,0x02002000),
                                  (UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x02020001)):
                    cpu.reg_write(reg,value)
                cpu.emu_start(values['NORMAL_FORMAT']|1,0x02020000,count=100000)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_PC),0x02020000)
                self.assertEqual(cpu.reg_read(UC_ARM_REG_SP),0x03007e00)
                self.assertEqual(len(seen),1)
                self.assertEqual(len(formatter_calls),0 if int(row['original_start'],16) in plain_sources else 1)
                self.assertEqual(bytes(cpu.mem_read(0x02001000,len(name_raw))),name_raw)
                if is_name:
                    expected=name_raw if mutable else prepared_copy(name[0]['binding_id'],name_raw,0x08000000+int(name[0]['original_start'],16))
                    self.assertEqual(seen[0][1],expected)
                else:
                    cpu.hook_del(handle)
                    expected_template=prepared_copy(row['binding_id'],raw,source)
                    cpu.mem_write(0x02003000,expected_template)
                    for reg,value in ((UC_ARM_REG_R0,0x02004000),(UC_ARM_REG_R1,0x02003000),(UC_ARM_REG_R2,0x02002004),
                                      (UC_ARM_REG_SP,0x03007e00),(UC_ARM_REG_LR,0x02020001)):
                        cpu.reg_write(reg,value)
                    cpu.emu_start(0x08002649,0x02020000,count=100000)
                    self.assertEqual(seen[0][1],text_at(0x02004000))

    def test_source_gate_reuses_exact_directories_and_excludes_unproved_routes(self):
        from halfspace_compact import KEYBOARD
        rows = compact_rows(self.image, self.corpus, self.link, self.components)
        foreign = {0x082b95bc, 0x082bd510, 0x082c7810, 0x082c78b8}
        excluded = foreign | {int(r['original_start'], 16)+0x08000000
                              for r, _ in rows if r['binding_id'] in KEYBOARD}
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        cpu.mem_map(0x08000000, 0x800000)
        cpu.mem_map(0x02000000, 0x40000)
        cpu.mem_map(0x03000000, 0x8000)
        cpu.mem_write(0x08000000, self.candidate)
        values = {'SOURCE_EXCLUSION_COUNT': len(excluded),
                  'COMPACT_SOURCE_LOOKUP': 0x08070100, 'SOURCE_EXCLUSIONS': 0x08070200}
        for name, offset in (('source_gate', 0x70000), ('source_lookup', 0x70100)):
            source = (ROOT/('asm/halfspace_compact_'+name+'.s')).read_text(encoding='utf-8')
            for key, value in values.items(): source = source.replace(key, hex(value))
            code = assemble(source, offset)
            self.assertLessEqual(len(code), 126)
            cpu.mem_write(0x08000000+offset, code)
        cpu.mem_write(0x08070200, b''.join(struct.pack('<I', v) for v in sorted(excluded)))

        def gate(pointer):
            for reg, value in ((UC_ARM_REG_R0, pointer), (UC_ARM_REG_R4, 0x12345678),
                               (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, 0x02020001)):
                cpu.reg_write(reg, value)
            cpu.emu_start(0x08070001, 0x02020000, count=4000)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x02020000)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R4), 0x12345678)
            return cpu.reg_read(UC_ARM_REG_R0) != 0

        for row, _ in rows:
            source = int(row['original_start'], 16)+0x08000000
            if row['variant_selection'] != 1:
                source += 0x02000000 if row['variant_selection'] == 11 else 0x04000000
            expected = row['binding_id'] not in KEYBOARD and not row['binding_id'].startswith(('SELECT_JOB_', 'SELECT_MONSTER_'))
            self.assertEqual(gate(source), expected, row['binding_id'])
        for source in (*foreign, 0x082bcfe0, 0x02001000, 0x03001460,
                       0x0e2bcfe0, 0x0a2b2cac, 0x082b2cad, 0x08000000):
            self.assertFalse(gate(source), hex(source))

    def test_marked_numeric_policy_matches_host_and_native_number_anchors(self):
        from halfspace_compact_consumers import NUMERIC_COLUMNS, prepared_copy
        rows = compact_rows(self.image, self.corpus, self.link, self.components)
        cpu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        for address, size in ((0x08000000, 0x800000), (0x02000000, 0x40000), (0x03000000, 0x8000)):
            cpu.mem_map(address, size)
        cpu.mem_write(0x08000000, self.candidate)
        for name, address in (('consumers_mark', 0x02020000), ('numeric_policy', 0x02020200)):
            source = (ROOT/('asm/halfspace_compact_'+name+'.s')).read_text(encoding='utf-8')
            source = source.replace('NUMERIC_POLICY', '0x02021000')
            code = assemble(source, address)
            if name == 'numeric_policy': self.assertLessEqual(len(code), 126)
            cpu.mem_write(address, code)
        cpu.mem_write(0x02021000, b''.join(struct.pack('<IBBxx', *v) for v in NUMERIC_COLUMNS.values()))

        def call(address, r0, r1, r2):
            saved = {reg: 0x12340000+reg for reg in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7)}
            for reg, value in saved.items(): cpu.reg_write(reg, value)
            for reg, value in ((UC_ARM_REG_R0, r0), (UC_ARM_REG_R1, r1), (UC_ARM_REG_R2, r2),
                               (UC_ARM_REG_SP, 0x03007e00), (UC_ARM_REG_LR, 0x02030001)):
                cpu.reg_write(reg, value)
            cpu.emu_start(address | 1, 0x02030000, count=100000)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), 0x02030000)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_SP), 0x03007e00)
            for reg, value in saved.items(): self.assertEqual(cpu.reg_read(reg), value)

        def format_native(template, number):
            cpu.mem_write(0x02001000, template)
            cpu.mem_write(0x02004000, b'X Y\0')
            values = [number]*4
            if b'%s' in template: values[0] = 0x02004000
            cpu.mem_write(0x02002000, struct.pack('<4I', *values))
            cpu.mem_write(0x02003000, b'\xa5'*320)
            call(0x08002648, 0x02003000, 0x02001000, 0x02002000)
            raw = bytes(cpu.mem_read(0x02003000, 320))
            end = raw.index(0)
            self.assertEqual(raw[end+1:], b'\xa5'*(319-end))
            return raw[:end+1]

        def digits(payload):
            # The twelve numeric templates use Hangul, ASCII, LF and clear10.
            x, line, offset, result = 0, 0, 0, []
            while payload[offset]:
                byte = payload[offset]
                if byte == 127:
                    offset += 3; x += 8; continue
                if byte in (10, 16):
                    x = 0; line += 1
                elif byte == 17:
                    pass
                else:
                    if 48 <= byte <= 57: result.append((byte, line, x))
                    x += 4 if byte == 31 else 8
                offset += 1
            return result

        for row, tokens in rows:
            binding = row['binding_id']
            raw = b''.join(tokens)+b'\0'
            source = int(row['original_start'], 16)+0x08000000
            expected = prepared_copy(binding, raw, source)
            cpu.mem_write(0x02001000, b'\xa5'*320)
            cpu.mem_write(0x02001000, raw)
            call(0x02020000, 0x02001000, len(raw), source)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R0), 1, binding)
            call(0x02020200, 0x02001000, len(raw), source)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R0), 1, binding)
            self.assertEqual(cpu.reg_read(UC_ARM_REG_R1), len(expected), binding)
            actual = bytes(cpu.mem_read(0x02001000, len(expected)))
            # Source gate excludes the keyboard before invoking either helper.
            from halfspace_compact import KEYBOARD
            if binding not in KEYBOARD: self.assertEqual(actual, expected, binding)
            self.assertEqual(bytes(cpu.mem_read(0x02001000+len(expected), 320-len(expected))),
                             b'\xa5'*(320-len(expected)))
            if b'%' not in tokens: continue
            for number in (0, 1, 42, 9999, 0xffffffff, 0x7fffffff):
                output = format_native(expected, number)
                self.assertEqual(output, format_native(actual, number), binding)
                if binding in NUMERIC_COLUMNS:
                    self.assertEqual(digits(output), digits(format_native(raw, number)), (binding, number))
                if b'%s' in raw: self.assertIn(b'X Y', output)


class InstalledNormalConsumerTests(NormalCompactComponentTests):
    @classmethod
    def setUpClass(cls):
        from halfspace_compact import normal_overlay
        CurrentROMConsumerTests.setUpClass.__func__(cls)
        cls.h3=cls.candidate
        cls.candidate,cls.normal_report=normal_overlay(cls.h3,cls.image,cls.link,cls.corpus,cls.components)

    def normal_components(self):
        values=dict(self.normal_report['symbols'])
        values.update(NORMAL_SMALL=0x08001ac8,NORMAL_SIMPLE=0x08001df0,NORMAL_FORMAT=0x08001dbc)
        return values,[]

    def test_direct_scanner_skip_uses_armv4t_and_preserves_native_scanner(self):
        from halfspace_compact import normal_overlay
        direct,report=normal_overlay(self.h3,self.image,self.link,self.corpus,self.components)
        self.assertEqual(direct[0xc5d4a:0xc5dac],self.h3[0xc5d4a:0xc5dac])
        self.assertEqual(direct[0x35d280:0x35d284],bytes.fromhex('c046c046'))
        cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        cpu.mem_map(0x08000000,0x800000);cpu.mem_write(0x08000000,direct)
        cpu.reg_write(UC_ARM_REG_R8,0x12345678)
        cpu.reg_write(UC_ARM_REG_CPSR,0xa0000030)
        cpu.emu_start(0x0835d281,0x0835d284,count=2)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_R8),0x12345678)
        self.assertEqual(cpu.reg_read(UC_ARM_REG_CPSR),0xa0000030)

    def test_installed_writes_preserve_size_original_pointers_and_live_prefixes(self):
        from halfspace_retired_owners import manifest,checked_writes
        self.assertEqual(len(self.candidate),0x800000)
        for row in self.corpus['rows']:
            at=int(row['pointer_storage'],16)
            self.assertEqual(self.candidate[at:at+4],self.image[at:at+4])
        for owner in manifest()['owners']:
            self.assertEqual(self.candidate[owner['start']:owner['reclaim_start']],self.h3[owner['start']:owner['reclaim_start']])
        approved=checked_writes(self.normal_report['writes'])
        self.assertEqual(len(approved),len(self.normal_report['writes'])-3)
        allowed={i for w in self.normal_report['writes'] for i in range(w['start'],w['end'])}
        self.assertTrue(all(a==b or n in allowed for n,(a,b) in enumerate(zip(self.h3,self.candidate))))


if __name__ == '__main__': unittest.main()

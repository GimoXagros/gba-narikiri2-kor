"""Public fail-closed guards; no private ROM is required."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from build_v11b import INPUTS, main, merge_graphics, rebuild, sha, flatten_compact_writes


class V11bBuildGuards(unittest.TestCase):
    def test_chained_allocator_revision_rejects_tampering_and_other_overlaps(self):
        before = bytes(0x800000)
        middle = bytearray(before)
        middle[0x35D23C:0x35D2C4] = b'A' * 136
        middle[0x35D26E:0x35D272] = bytes.fromhex('68f56cfd')
        middle[0x35D280:0x35D284] = bytes.fromhex('68f563fd')
        after = bytearray(middle)
        after[0x35D26E:0x35D272] = b'BBBB'
        after[0x35D280:0x35D284] = bytes.fromhex('c046c046')
        def record(old, new, lo, hi, owner):
            return dict(start=lo, end=hi, owner=owner,
                        before_sha256=sha(old[lo:hi]), after_sha256=sha(new[lo:hi]))
        first = [record(before, middle, 0x35D23C, 0x35D2C4, 'private_batch_allocate')]
        second = [record(middle, after, p, p+4, 'revision') for p in (0x35D26E, 0x35D280)]
        result = flatten_compact_writes(before, middle, after, first, second)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['after_sha256'], sha(after[0x35D23C:0x35D2C4]))
        tampered = bytearray(after); tampered[10] = 1
        with self.assertRaisesRegex(ValueError, 'Undeclared'):
            flatten_compact_writes(before, middle, tampered, first, second)
        with self.assertRaisesRegex(ValueError, 'postimage'):
            flatten_compact_writes(before, middle, middle, first, second)
        other = bytearray(middle); other[0x35D250:0x35D254] = b'CCCC'
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            flatten_compact_writes(before, middle, other, first,
                [record(middle, other, 0x35D250, 0x35D254, 'foreign')])
        partial = bytearray(middle); partial[0x35D26E:0x35D272] = b'BBBB'
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            flatten_compact_writes(before, middle, partial, first, second[:1])
        foreign = bytearray(middle); foreign[0x35D26E:0x35D272] = b'XXXX'
        forged_first = [record(before, foreign, 0x35D23C, 0x35D2C4, 'private_batch_allocate')]
        forged_second = [record(foreign, after, p, p+4, 'revision') for p in (0x35D26E, 0x35D280)]
        with self.assertRaisesRegex(ValueError, 'call preimage'):
            flatten_compact_writes(before, foreign, after, forged_first, forged_second)
        thumb2 = bytearray(after); thumb2[0x35D280:0x35D284] = bytes.fromhex('00bf00bf')
        modern = [record(middle, thumb2, p, p+4, 'revision') for p in (0x35D26E, 0x35D280)]
        with self.assertRaisesRegex(ValueError, 'ARM7-compatible'):
            flatten_compact_writes(before, middle, thumb2, first, modern)

    def test_wrong_source_stops_before_optional_dependencies(self):
        with self.assertRaisesRegex(ValueError, 'Japanese source mismatch'):
            rebuild(b'wrong', b'', {}, {}, {}, '0'*64)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory)/'keep'
            marker.write_bytes(b'original')
            argv = ['build_v11b.py', '--out', directory, '--expected-target', '0'*64]
            for key in ('japanese', *INPUTS):
                argv.extend(['--'+key.replace('_','-'), 'missing'])
            with patch.object(sys, 'argv', argv), self.assertRaisesRegex(ValueError, 'already exists'):
                main()
            self.assertEqual(marker.read_bytes(), b'original')

    def test_graphic_owner_merge_rejects_conflicts_and_tampering(self):
        base = bytes(0x800000)
        graphics = bytearray(base)
        graphics[16:18] = b'ab'
        write = dict(start=16, bytes=2, before_sha256=sha(b'\0\0'), after_sha256=sha(b'ab'))
        self.assertEqual(merge_graphics(base, base, graphics, [write]), graphics)
        conflict = bytearray(base)
        conflict[16] = 1
        for runtime, image, writes in [(conflict, graphics, [write]),
                (base, base, [write]), (base, graphics, [write, write])]:
            with self.subTest(writes=writes), self.assertRaises(ValueError):
                merge_graphics(runtime, base, image, writes)


if __name__ == '__main__':
    unittest.main()

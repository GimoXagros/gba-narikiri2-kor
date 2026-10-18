"""Public guards use synthetic bytes; private release data is never required."""
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_v11a import INPUTS, checked_read, main, rebuild, sha, validate_writes


class V11aGuards(unittest.TestCase):
    def test_checked_input_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.json'
            source.write_bytes(b'[]')
            expected = sha(source.read_bytes())
            self.assertEqual(checked_read(source, expected), b'[]')
            source.write_bytes(b'[{}]')
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                checked_read(source, expected)

    def test_wrong_japanese_source_stops_before_patch_decode(self):
        with self.assertRaisesRegex(ValueError, 'Japanese source mismatch'):
            rebuild(b'wrong source', b'not a patch', [], {}, {}, {})

    def test_existing_output_is_never_touched(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'keep'
            marker.write_bytes(b'preserve')
            argv = ['build_v11a.py', '--out', directory]
            for name in ('japanese', *INPUTS):
                argv.extend(['--' + name.replace('_', '-'), 'missing-input'])
            with patch.object(sys, 'argv', argv):
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    main()
            self.assertEqual(marker.read_bytes(), b'preserve')

    def test_write_ranges_reject_overlap_and_protection(self):
        for writes, protected, size in [
            ({2: b'abc', 4: b'xy'}, [], 10),
            ({2: b'abc'}, [(4, 6)], 10),
            ({9: b'xy'}, [], 10),
            ({-1: b'x'}, [], 10),
        ]:
            with self.subTest(writes=writes, protected=protected):
                with self.assertRaises(ValueError):
                    validate_writes(writes, protected, size)
        self.assertEqual(validate_writes({4: b'xy', 2: b'ab'}, [(0, 2), (6, 8)], 8), [(2, b'ab'), (4, b'xy')])


if __name__ == '__main__':
    unittest.main()

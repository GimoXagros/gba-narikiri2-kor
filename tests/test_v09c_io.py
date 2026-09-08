"""Storage-failure contracts without game data; every directory is isolated."""
import errno
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import v09c_io as io


class FailingWriter:
    def __init__(self, stream):
        self.stream = stream
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.stream.close()
    def write(self, data):
        self.stream.write(data[:128])
        self.stream.flush()
        raise OSError(errno.ENOSPC, 'Injected storage exhaustion after 128 bytes')


class CandidateOutputTests(unittest.TestCase):
    def test_unicode_path_success(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)/'검증 파일 [AN9J].gba'
            io.atomic_write_new(out, b'candidate'*200)
            self.assertEqual(out.read_bytes(), b'candidate'*200)
            self.assertEqual(list(Path(directory).iterdir()), [out])

    def test_partial_write_leaves_no_final_or_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)/'candidate.gba'
            original = Path.open
            def open_file(path, mode='r', *args, **kwargs):
                stream = original(path, mode, *args, **kwargs)
                return FailingWriter(stream) if mode == 'xb' else stream
            with patch.object(Path, 'open', open_file), self.assertRaises(OSError):
                io.atomic_write_new(out, b'candidate'*200)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_flush_failure_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(io.os, 'fsync', side_effect=OSError('Injected fsync failure')):
                with self.assertRaises(OSError):
                    io.atomic_write_new(Path(directory)/'candidate.gba', b'data')
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_readback_failure_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(Path, 'read_bytes', return_value=b'damaged'):
                with self.assertRaises(OSError):
                    io.atomic_write_new(Path(directory)/'candidate.gba', b'correct')
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_existing_file_and_hardlink_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory)/'reference.gba'; original.write_bytes(b'personal data')
            alias = Path(directory)/'alias.gba'; os.link(original, alias)
            for out in (original, alias):
                with self.assertRaises(FileExistsError): io.atomic_write_new(out, b'new')
            self.assertEqual(original.read_bytes(), b'personal data')
            self.assertEqual(alias.read_bytes(), b'personal data')

    def test_concurrent_destination_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)/'candidate.gba'
            operation = 'rename' if os.name == 'nt' else 'link'
            publish = getattr(io.os, operation)
            def raced(source, destination):
                out.write_bytes(b'concurrent user file')
                return publish(source, destination)
            with patch.object(io.os, operation, raced), self.assertRaises(FileExistsError):
                io.atomic_write_new(out, b'candidate')
            self.assertEqual(out.read_bytes(), b'concurrent user file')
            self.assertEqual(list(Path(directory).iterdir()), [out])


if __name__ == '__main__': unittest.main()

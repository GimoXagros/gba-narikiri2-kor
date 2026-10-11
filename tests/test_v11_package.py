"""Synthetic packaging and write-failure tests; no game data or final BPS pin."""
import copy
import errno
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import apply_japanese_patch_v11 as app
import package_v11 as pkg
import v09c_io as safeio
from bps import create_bps


class WriteProxy:
    def __init__(self, stream, mode):
        self.stream, self.mode = stream, mode
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.stream.close()
    def write(self, data):
        if self.mode == 'enospc':
            self.stream.write(data[:3])
            raise OSError(errno.ENOSPC, 'Synthetic ENOSPC')
        return self.stream.write(data[:-1])
    def flush(self):
        self.stream.flush()
    def fileno(self):
        return self.stream.fileno()


class V11PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = b'synthetic original source' * 4
        self.target = b'synthetic modified target' * 4
        self.delta = create_bps(self.source, self.target)
        for key, value in dict(SOURCE_SIZE=len(self.source), TARGET_SIZE=len(self.target),
                               SOURCE_SHA256=app.sha(self.source), TARGET_SHA256=app.sha(self.target),
                               PATCH_SIZE=len(self.delta), PATCH_SHA256=app.sha(self.delta)).items():
            context = patch.object(app, key, value)
            context.start()
            self.addCleanup(context.stop)
        self.manifest = dict(schema=app.SCHEMA, version='v1.1',
            source=dict(size=len(self.source), sha256=app.sha(self.source)),
            target=dict(size=len(self.target), sha256=app.sha(self.target)),
            patch=dict(name=app.PATCH_NAME, size=len(self.delta), sha256=app.sha(self.delta)))
        self.src, self.bps, self.pin, self.out = (self.directory / n for n in
            ('入力 日本語.gba', app.PATCH_NAME, app.MANIFEST_NAME, '새 결과.gba'))
        self.src.write_bytes(self.source)
        self.bps.write_bytes(self.delta)
        self.pin.write_text(json.dumps(self.manifest), encoding='utf-8')
        self.docs = self.directory / 'documents'
        self.docs.mkdir()
        for name in app.DOCUMENT_NAMES:
            (self.docs / name).write_text('Synthetic public text.\n', encoding='utf-8')
        verification = dict(version='v1.1', source_sha256=app.sha(self.source),
                            target_sha256=app.sha(self.target), patch_sha256=app.sha(self.delta),
                            release_eligible=False, hardware_status='NOT_RUN')
        (self.docs / 'VERIFICATION.json').write_text(json.dumps(verification), encoding='utf-8')

    def apply(self, out=None):
        return app.apply(self.src, self.bps, out or self.out, self.pin)

    def package(self, manifest=None, target=None):
        return pkg.package(self.source, self.target if target is None else target,
                           self.delta, self.manifest if manifest is None else manifest, self.docs)

    def test_apply_unicode_and_exact_target(self):
        self.assertEqual(self.apply(), app.sha(self.target))
        self.assertEqual(self.out.read_bytes(), self.target)
        self.assertEqual(self.src.read_bytes(), self.source)

    def test_source_identity_rejected_without_output(self):
        self.src.write_bytes(self.source[:-1])
        with self.assertRaisesRegex(ValueError, 'unmodified'): self.apply()
        self.assertFalse(self.out.exists())

    def test_patch_hash_rejected_without_output(self):
        self.bps.write_bytes(self.delta + b'x')
        with self.assertRaisesRegex(ValueError, 'Patch identity'): self.apply()
        self.assertFalse(self.out.exists())

    def test_patch_crc_rejected_even_with_matching_manifest_hash(self):
        bad = self.delta[:-1] + bytes((self.delta[-1] ^ 1,))
        manifest = copy.deepcopy(self.manifest)
        manifest['patch']['sha256'] = app.sha(bad)
        with patch.object(app, 'PATCH_SHA256', app.sha(bad)):
            with self.assertRaisesRegex(ValueError, 'CRC32'): app.verify_patch(self.source, bad, manifest)

    def test_final_target_rejected_even_for_valid_bps(self):
        bad = create_bps(self.source, self.source)
        manifest = copy.deepcopy(self.manifest)
        manifest['patch'].update(size=len(bad), sha256=app.sha(bad))
        with patch.object(app, 'PATCH_SHA256', app.sha(bad)), patch.object(app, 'PATCH_SIZE', len(bad)):
            with self.assertRaisesRegex(ValueError, 'target identity'): app.verify_patch(self.source, bad, manifest)

    def test_wrong_version_source_target_or_unknown_fields(self):
        for key, value in (('version', 'v1.0'), ('source', dict(size=app.SOURCE_SIZE, sha256='0'*64)),
                           ('target', dict(size=app.TARGET_SIZE, sha256='0'*64)), ('private_path', 'x')):
            with self.subTest(key=key):
                manifest = dict(self.manifest, **{key: value})
                with self.assertRaises(ValueError): app.validate_manifest(manifest)

    def test_patch_name_hash_size_types_and_placeholder_rejected(self):
        for key, value in (('name', '../game.bps'), ('size', True), ('size', 0),
                           ('sha256', None), ('sha256', 'PENDING'), ('sha256', 'A'*64)):
            with self.subTest(key=key, value=value):
                manifest = copy.deepcopy(self.manifest)
                manifest['patch'][key] = value
                with self.assertRaises(ValueError): app.validate_manifest(manifest)

    def test_no_existing_output_or_input_overwrite(self):
        self.out.write_bytes(b'personal data')
        for output in (self.out, self.src, self.bps, self.pin):
            with self.subTest(output=output), self.assertRaises(FileExistsError): self.apply(output)
        self.assertEqual(self.out.read_bytes(), b'personal data')
        self.assertEqual(self.src.read_bytes(), self.source)
        self.assertEqual(self.bps.read_bytes(), self.delta)

    def test_hardlinked_output_keeps_original(self):
        os.link(self.src, self.out)
        with self.assertRaises(FileExistsError): self.apply()
        self.assertEqual(self.out.read_bytes(), self.source)

    def test_real_dangling_and_existing_symlink_outputs(self):
        try:
            self.out.symlink_to(self.directory / 'missing')
        except OSError as exc:
            self.skipTest('Actual symlink NOT_RUN: platform privilege unavailable: ' + str(exc))
        with self.assertRaises(FileExistsError): self.apply()
        self.assertTrue(self.out.is_symlink())
        self.out.unlink()
        self.out.symlink_to(self.src)
        with self.assertRaises(FileExistsError): self.apply()
        self.assertEqual(self.src.read_bytes(), self.source)

    def test_dangling_symlink_check_without_platform_privilege(self):
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda p: p == self.out or original(p)):
            with self.assertRaises(FileExistsError): self.apply()
        self.assertFalse(self.out.exists())

    def test_publication_race_preserves_concurrent_file(self):
        operation = 'rename' if os.name == 'nt' else 'link'
        original = getattr(safeio.os, operation)
        def raced(source, destination):
            self.out.write_bytes(b'concurrent user file')
            return original(source, destination)
        with patch.object(safeio.os, operation, raced), self.assertRaises(FileExistsError): self.apply()
        self.assertEqual(self.out.read_bytes(), b'concurrent user file')
        self.assertEqual(list(self.directory.glob('.*.tmp')), [])

    def test_short_write_and_partial_enospc_cleanup(self):
        original = Path.open
        for mode in ('short', 'enospc'):
            with self.subTest(mode=mode):
                def open_file(path, access='r', *args, **kwargs):
                    access = kwargs.pop('mode', access)
                    stream = original(path, access, *args, **kwargs)
                    return WriteProxy(stream, mode) if access == 'xb' else stream
                with patch.object(Path, 'open', open_file), self.assertRaises(OSError): self.apply()
                self.assertFalse(self.out.exists())
                self.assertEqual(list(self.directory.glob('.*.tmp')), [])

    def test_fsync_enospc_cleanup(self):
        with patch.object(safeio.os, 'fsync', side_effect=OSError(errno.ENOSPC, 'Synthetic fsync ENOSPC')):
            with self.assertRaises(OSError): self.apply()
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.directory.glob('.*.tmp')), [])

    def test_staged_readback_failure_cleanup(self):
        original = Path.read_bytes
        def read(path):
            return b'corrupt' if path.name.endswith('.tmp') else original(path)
        with patch.object(Path, 'read_bytes', read), self.assertRaisesRegex(OSError, 'Staged'): self.apply()
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.directory.glob('.*.tmp')), [])

    def test_published_readback_failure_cleanup(self):
        original = Path.read_bytes
        def read(path):
            return b'corrupt' if path == self.out else original(path)
        with patch.object(Path, 'read_bytes', read), self.assertRaisesRegex(OSError, 'Published'): self.apply()
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.directory.glob('.*.tmp')), [])

    def test_package_deterministic_and_only_public_allowlist(self):
        (self.docs / 'personal.sav').write_bytes(b'private')
        (self.docs / 'full_script.csv').write_bytes(b'private')
        first, second = self.package(), self.package()
        self.assertEqual(first, second)
        with zipfile.ZipFile(BytesIO(first)) as archive:
            self.assertEqual(set(archive.namelist()), pkg.ARCHIVE_NAMES)
            self.assertEqual(len(archive.namelist()), 13)
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read(app.PATCH_NAME), self.delta)
            manifest = json.loads(archive.read('manifest.json'))
            app.validate_manifest(manifest)
            for name, record in manifest['files'].items():
                data = archive.read(name)
                self.assertEqual(record, dict(size=len(data), sha256=app.sha(data)))
            sums = archive.read('SHA256SUMS.txt').decode('ascii').splitlines()
            self.assertEqual(len(sums), 12)
            for line in sums:
                digest, name = line.split('  ', 1)
                self.assertEqual(digest, app.sha(archive.read(name)))

    def test_provided_target_not_bps_target_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Provided final target'): self.package(target=self.source)

    def test_untrusted_manifest_cannot_select_another_patch(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['patch']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'reviewed clean build'): app.validate_manifest(manifest)

    def test_public_license_links_are_allowed(self):
        (self.docs / 'RIGHTS.md').write_text('See https://example.org/license and http://example.org/about\n', encoding='utf-8')
        self.assertTrue(self.package())

    def test_missing_required_document_rejected(self):
        (self.docs / 'RIGHTS.md').unlink()
        with self.assertRaises(FileNotFoundError): self.package()

    def test_private_paths_and_binary_docs_rejected(self):
        for text in ('C:\\Users\\someone\\private.txt', '/home/someone/a',
                     'private_validation/a.json', 'binary\0data'):
            with self.subTest(text=text):
                (self.docs / 'README.txt').write_text(text, encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'Non-public'): self.package()

    def test_verification_pin_mismatch_rejected(self):
        doc = self.docs / 'VERIFICATION.json'
        verification = json.loads(doc.read_text(encoding='utf-8'))
        verification['target_sha256'] = '0' * 64
        doc.write_text(json.dumps(verification), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Verification'): self.package()

    def test_candidate_cannot_claim_release_or_hardware_approval(self):
        doc = self.docs / 'VERIFICATION.json'
        original = json.loads(doc.read_text(encoding='utf-8'))
        for key, value in (('release_eligible', True), ('hardware_status', 'PASS')):
            with self.subTest(key=key):
                doc.write_text(json.dumps(dict(original, **{key: value})), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'Candidate verification'): self.package()

    def test_manifest_extra_payload_path_rejected(self):
        with zipfile.ZipFile(BytesIO(self.package())) as archive:
            manifest = json.loads(archive.read('manifest.json'))
        manifest['files']['personal.sav'] = dict(size=0, sha256='0'*64)
        with self.assertRaisesRegex(ValueError, 'allowlist'): self.package(manifest=manifest)

    def test_manifest_actual_public_payload_mismatch_rejected(self):
        with zipfile.ZipFile(BytesIO(self.package())) as archive:
            manifest = json.loads(archive.read('manifest.json'))
        manifest['files']['RIGHTS.md']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'actual public files'): self.package(manifest=manifest)


if __name__ == '__main__':
    unittest.main()

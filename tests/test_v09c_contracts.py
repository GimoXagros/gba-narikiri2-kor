"""Real frozen release vs PC candidate regression; ROM bytes remain unchanged."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
import apply_ffr_v09b as old
import apply_ffr_v09c as new
from build_ffr_v09c import candidate_manifest
from package_ffr_v09c_release import validate_manifest
from narikiri2_text_spec import JAPANESE_SHA256
from test_v09c_io import FailingWriter


class CandidateContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = ROOT/'private_validation/v09b-repro-A'
        cls.rom = (cls.base/(old.NAME+'.gba')).read_bytes()
        cls.bps = (cls.base/(old.NAME+'_FROM_BETA3.bps')).read_bytes()
        cls.source = (ROOT/'BETA3-reference.gba').read_bytes()
        cls.gate = json.loads((ROOT/'verification/v0.9b.json').read_text(encoding='utf-8'))
        cls.manifest = candidate_manifest(cls.rom, cls.bps, dict(first_stage_pointer_bindings=2077,
                                                               japanese_review=cls.gate['japanese_review']))
        cls.manifest.update(japanese_reference_sha256_before=JAPANESE_SHA256,
                            japanese_reference_sha256_after=JAPANESE_SHA256,
                            beta3_source_sha256_before=new.SOURCE, beta3_source_sha256_after=new.SOURCE)

    def test_same_fault_fails_old_contract_and_passes_candidate_contract(self):
        original = Path.open
        def opened(path, mode='r', *args, **kwargs):
            stream = original(path, mode, *args, **kwargs)
            return FailingWriter(stream) if mode == 'xb' else stream
        observations = {}
        for app in (old, new):
            with tempfile.TemporaryDirectory() as directory:
                out = Path(directory)/'candidate.gba'
                argv = ['apply', str(ROOT/'BETA3-reference.gba'), '--patch',
                        str(self.base/(old.NAME+'_FROM_BETA3.bps')), '--output', str(out)]
                with patch.object(sys, 'argv', argv), patch.object(Path, 'open', opened):
                    with self.assertRaises(OSError): app.main()
                observations[app.__name__] = out.exists()
                if out.exists(): self.assertEqual(out.stat().st_size, 128)
        self.assertEqual(observations, {'apply_ffr_v09b': True, 'apply_ffr_v09c': False})

    def test_valid_manifest_and_cumulative_application(self):
        validate_manifest(self.manifest, self.rom, self.bps, self.gate)
        self.assertEqual(new.checked(self.source, self.bps), self.rom)

    def test_version_size_authority_and_provenance_mismatches_rejected(self):
        for key, bad in [('version', 'WRONG_VERSION'), ('source_size', 1), ('patch_size', 2),
                         ('target_size', 1), ('release_authorized', True), ('rom_changes', ['unowned']),
                         ('baseline_v09b_sha256', '0'*64), ('compact_name_fields', 2077),
                         ('source_size', float(self.manifest['source_size']))]:
            changed = copy.deepcopy(self.manifest); changed[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_manifest(changed, self.rom, self.bps, self.gate)

    def test_extra_and_missing_metadata_rejected(self):
        for changed in (dict(self.manifest, invented=True),
                        {k:v for k,v in self.manifest.items() if k != 'source_size'}):
            with self.assertRaises(ValueError): validate_manifest(changed, self.rom, self.bps, self.gate)
        changed = copy.deepcopy(self.manifest)
        changed['baseline_review']['trade_pointer_table_restored'] = 1
        with self.assertRaises(ValueError): validate_manifest(changed, self.rom, self.bps, self.gate)

    def test_wrong_source_repatch_and_damaged_patch_rejected(self):
        for wrong in (b'', self.rom, self.source[:-1]):
            with self.assertRaises(ValueError): new.checked(wrong, self.bps)
        with self.assertRaises(ValueError): new.checked(self.source, self.bps[:-1]+bytes([self.bps[-1]^1]))


if __name__ == '__main__': unittest.main()

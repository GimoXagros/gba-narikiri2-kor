"""Check public tracked files and active source dependencies without ROM inputs.

This gate complements the recorded manual source/licensing review. It does not
authorize arbitrary binary patches or prove translation or game correctness.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOGO = 'a6d33ce289482f8c5adbb3afc1672a34c1a4a3cfbb30a437c8d864ad7cd1cf0f'


def inspect_content(name, data):
    path = Path(name)
    if name == 'logo.png':
        if hashlib.sha256(data).hexdigest() != LOGO:
            raise ValueError('Original logo identity changed')
        return
    if path.suffix.lower() in {'.gba', '.sav', '.rom', '.bin', '.zip', '.bps', '.ips', '.dll', '.exe', '.state'}:
        raise ValueError('Private/binary artifact in public files: ' + name)
    if data.startswith((b'PK\x03\x04', b'BPS1', b'PATCH', b'\x7fELF', b'MZ', b'\x89PNG')) or b'\x00' in data:
        raise ValueError('Disguised binary content: ' + name)
    text = data.decode('utf-8-sig')
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', text):
        raise ValueError('Private key in public source')
    if re.search(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})', text):
        raise ValueError('Credential-shaped public content')
    if path.suffix in {'.py', '.mjs', '.yml', '.yaml'}:
        old_repo = 'narikiri2-' + 'an9j-save-fix'
        personal_path = r'[A-Za-z]:[\\/]Users[\\/]|/' + r'Users/[^/]+/'
        if old_repo in text or re.search(personal_path, text):
            raise ValueError('Active source depends on a legacy/personal location: ' + name)


def audit(root=ROOT):
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode('utf-8').split('\0')
    files = [n for n in names if n]
    for name in files:
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Tracked file resolves outside checkout: ' + name)
        inspect_content(name, path.read_bytes())
    font = root / 'third_party/_work'
    if font.exists() and not font.resolve().is_relative_to(root.resolve()):
        raise ValueError('Font work directory depends on another checkout')
    return {'status': 'PASS', 'tracked_files': len(files), 'rom_inputs_required': False,
            'scope': 'Public content signatures, logo identity and active dependency paths; manual rights review remains required'}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))

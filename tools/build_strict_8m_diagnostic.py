"""Rebuild the integrated diagnostic from explicit local source inputs.

The output is never release eligible. Runtime, alias reachability, performance,
save and final-hash hardware gates remain separate from byte reproducibility.
No private emulator harness, intermediate ROM or test package is imported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from bps import create_bps, apply_bps
from strict_text_bindings import require_image, JP_SHA256, BASELINE_SHA256
from v09c_io import atomic_write_new

ROOT=Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(japanese,adopted,catalog,audit,out):
    inputs=[Path(p).resolve() for p in (japanese,adopted,catalog,audit)]
    out=Path(out).resolve()
    if out.exists():raise FileExistsError('A fresh diagnostic output directory is required')
    jp,ko=inputs[0].read_bytes(),inputs[1].read_bytes()
    require_image(jp,JP_SHA256,0x800000,'Japanese source')
    require_image(ko,BASELINE_SHA256,13270790,'Adopted Korean source')
    identities={name:dict(size=p.stat().st_size,sha256=digest(p.read_bytes()))
        for name,p in zip(('japanese','adopted','catalog','audit'),inputs)}
    out.mkdir(parents=True,exist_ok=False)
    def run(script,arguments):
        command=[sys.executable,str(ROOT/'tools'/script),*map(str,arguments)]
        completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
        atomic_write_new(out/(script+'.log'),(completed.stdout+completed.stderr).encode('utf-8'))
        if completed.returncode:raise RuntimeError(f'{script} failed; inspect its diagnostic log')
    text,components,linked=out/'text',out/'components',out/'linked'
    run('build_jp8mib_strict.py',[
        '--japanese',inputs[0],'--baseline',inputs[1],'--catalog',inputs[2],
        '--audit',inputs[3],'--encoding','unit_inline','--out-dir',text])
    run('build_strict_runtime_components.py',[
        '--japanese',inputs[0],'--adopted',inputs[1],'--text-build',text,'--out',components])
    run('strict_runtime_linker.py',[
        '--japanese',inputs[0],'--adopted',inputs[1],
        '--probe',components/'RUNTIME_COMPONENT_SOURCE.bin','--build',components/'BUILD.json',
        '--text-build',text,'--owned-menus','--fast-full-draw','--out',linked])
    target=(linked/'FIXED_8MIB_DIAGNOSTIC_NOT_PRODUCT.gba').read_bytes()
    if len(target)!=0x800000:raise ValueError('Integrated ROM is not exactly 8 MiB')
    patch=create_bps(jp,target)
    if apply_bps(jp,patch)!=target:raise ValueError('Diagnostic BPS roundtrip differs')
    atomic_write_new(out/'FIXED_8MIB_DIAGNOSTIC_NOT_PRODUCT.bps',patch)
    source_files=sorted([*ROOT.joinpath('tools').glob('*.py'),*ROOT.joinpath('asm').glob('*.s')])
    source_files.extend(sorted(ROOT.joinpath('config').glob('*.json')))
    report=dict(status='INTEGRATED_DIAGNOSTIC_REPRODUCTION_ONLY',release_eligible=False,
        inputs=identities,python=sys.version.split()[0],target_size=len(target),target_sha256=digest(target),
        patch_size=len(patch),patch_sha256=digest(patch),bps_apply_exact=True,
        source_files={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in source_files},
        remaining_gates=['required game consumer closure','alias game-context reachability',
            'final ROM save and runtime regression','six-path performance','final-hash hardware','public source/package audit'])
    atomic_write_new(out/'REPRODUCTION.json',(json.dumps(report,indent=2)+'\n').encode('utf-8'))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('japanese','adopted','catalog','audit','out'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();report=build(**vars(args))
    print(json.dumps({k:report[k] for k in ('status','target_size','target_sha256','patch_sha256','release_eligible')}))


if __name__=='__main__':main()

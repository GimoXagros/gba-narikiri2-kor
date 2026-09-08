"""Replay explicitly supplied controller routes; report observations, not gameplay PASS.

Save exports are chained by the recorded input hash. Cross-ROM savestates are
never loaded. RAM setup remains marked as fixture evidence. Absolute paths and
screenshots belong only in the caller's private output directory.
"""
import argparse
import hashlib
import json
from pathlib import Path

from libretro_probe import Probe


def replay(rom, core, routes, save_roots, output):
    output.mkdir(parents=True, exist_ok=False)
    saves = {}
    for root in save_roots:
        for path in root.rglob('*.sav'):
            if path.stat().st_size == 8192:
                saves[hashlib.sha256(path.read_bytes()).hexdigest()] = path
    results = []
    for route in routes:
        rows = [json.loads(line) for line in route.read_text(encoding='utf-8-sig').splitlines()]
        initial = rows[0]['input_save_sha256']
        host = Probe(core, rom, output/route.parent.name, saves[initial] if initial else None)
        screens, exports = [], []
        try:
            for row in rows:
                request = row.get('request', {})
                op = request.get('op')
                if op in ('frames', 'write_ram'):
                    host.execute(request)
                elif op == 'screenshot':
                    result = host.execute(request)
                    screens.append(dict(name=request['name'], sha256=result['sha256'],
                                        prior_sha256=row['result']['sha256'],
                                        identical=result['sha256'] == row['result']['sha256']))
                elif op == 'save_export':
                    result = host.execute(request)
                    exports.append(result)
                    saves[row['result']['sha256']] = Path(result['path'])
                elif op == 'state_load':
                    raise ValueError('Savestate transfer is not allowed in this replay')
            party = int.from_bytes(host.read_memory(0x02003FF8, 4), 'little')
            names = ([host.read_memory(party+i*60, 32).hex() for i in range(2)]
                     if 0x02000000 <= party < 0x0203FF80 else [])
            results.append(dict(run=route.parent.name, route_sha256=hashlib.sha256(route.read_bytes()).hexdigest(),
                                status='OBSERVATIONS_REQUIRE_SEMANTIC_REVIEW', **host.status(),
                                party=names, screens=screens, exports=exports))
            (output/'observations.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(dict(run=route.parent.name, frame=host.frame,
                                  ram_interventions=host.ram_interventions,
                                  identical_screens=sum(s['identical'] for s in screens),
                                  total_screens=len(screens))), flush=True)
        finally:
            host.lib.retro_unload_game()
            host.lib.retro_deinit()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('rom', 'core', 'route_list', 'output'):
        parser.add_argument('--'+name.replace('_', '-'), type=Path, required=True)
    parser.add_argument('--save-root', type=Path, action='append', default=[])
    args = parser.parse_args()
    routes = [Path(p) for p in json.loads(args.route_list.read_text(encoding='utf-8-sig'))]
    replay(args.rom, args.core, routes, args.save_root, args.output)


if __name__ == '__main__':
    main()

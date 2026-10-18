"""Rebuild the accepted v1.1a image from explicitly supplied private inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from bps import apply_bps, create_bps
from narikiri2_text_spec import decode_game_text
from strict_default_names import unpack_name
from strict_packed_tree import unpack_tree
from strict_stream_lookup24 import unpack_bounds24
from strict_unit_codec import decode_parts

JP = 'a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'
BASE = '9fd341b827a8ba282781d7f8f214f2ba8641365b541564d53e9ef5267511889b'
TARGET = '8823db1cb72f1328136ccfd8fff1fbdca0c8489cbc7ccf90f7e4ecdbb1c37776'
INPUTS = {
    'baseline_patch': '4e4ad0229b22ea5bd8e6b351adfa79a749e2b5288aabb24d7d1e356a7bfafade',
    'plan': '001c62af251a199a102225ddac7db1d947bec3d34a67792eca5372cb19655a9a',
    'link': '82b143f8f7328a45a3a9af41d8284d6362dcda5003be6851a93095e0ce2260ee',
    'components': '5d45d6a100b95cff594c66c1308ac983198994de5a0c33f922f99cb81e3b9468',
    'corpus': 'acfbcdfe90c6e25d15e701cb6c01f31ad88aa365235f4493cc4c36cd218951b0',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def checked_read(path, expected):
    data = Path(path).read_bytes()
    require(sha(data) == expected, 'Input SHA-256 mismatch: ' + str(path))
    return data


def validate_writes(writes, protected, size):
    ordered = sorted(writes.items())
    for start, data in ordered:
        end = start + len(data)
        require(0 <= start < end <= size, 'Write outside image')
        require(all(end <= a or start >= b for a, b in protected), 'Protected range overlap')
    for (start, data), (following, _) in zip(ordered, ordered[1:]):
        require(start + len(data) <= following, 'Write overlap')
    return ordered


def rebuild(japanese, patch, plan, link, components, corpus):
    require(sha(japanese) == JP, 'Japanese source mismatch')
    image = apply_bps(japanese, patch)
    require(len(image) == 0x800000 and sha(image) == BASE, 'Baseline mismatch')
    segments = link['layout']['segments']
    require(len(segments) == 52, 'Segment count mismatch')
    segs = {s['name']: s for s in segments}
    books = {kind: unpack_tree(image[segs[name]['new']:segs[name]['new'] + segs[name]['size']])
             for kind, name in [('full_text', 'full_book'), ('compact', 'compact_book'), ('extra', 'extra_book')]}
    bs = segs['full_bounds']
    bounds = dict(unpack_bounds24(image[bs['new']:bs['new'] + bs['size']]))
    rows = {r['binding_id']: r for r in corpus['rows']}
    require(len(rows) == len(corpus['rows']) == 10371, 'Corpus count mismatch')
    require(len(plan) == len({r['binding_id'] for r in plan}) == 597, 'Plan count mismatch')
    require(all(r['status'] in ('REVIEWED_KEEP', 'FIT_PENDING_INDEPENDENT_CHECK') for r in plan), 'Unaccepted plan status')
    changes = {r['binding_id']: r for r in plan if r['status'] == 'FIT_PENDING_INDEPENDENT_CHECK'}
    require(len(changes) == 552, 'Change count mismatch')
    protected = [(s['new'], s['new'] + s['size']) for s in segments]
    protected += [(int(r['pointer_storage'], 16), int(r['pointer_storage'], 16) + 4) for r in rows.values()]
    writes = {}
    for binding, edit in changes.items():
        row = rows[binding]
        start, cap = int(row['current_start'], 16), int(row['original_slot_bytes'])
        raw, encoded = bytes.fromhex(edit['native_hex']), bytes.fromhex(edit['encoded_hex'])
        require(row['category'] == 'full_text' and int(row['variant_selection']) == 1, 'Unsupported edit binding')
        require(start == int(row['original_start'], 16) == edit['start'] and cap == edit['capacity'], 'Original slot mismatch')
        require(bounds[0x08000000 + start] == cap and len(encoded) <= cap and len(raw) + 1 <= 283, 'Capacity mismatch')
        old, _ = decode_parts(image[start:start + cap], books['full_text'], 283, 1, 1, allow_suffix=True)
        require(sha(old) == row['native_sha256'] and decode_game_text(image, old[:-1]) == edit['before'], 'Original native mismatch')
        require(decode_game_text(image, raw) == edit['after'], 'Reviewed text mismatch')
        decoded, used = decode_parts(encoded, books['full_text'], 283, 1, 1)
        require(decoded == raw + b'\0' and used == len(encoded), 'Encoded plan mismatch')
        require(start not in writes or writes[start] == encoded, 'Conflicting alias edits')
        writes[start] = encoded
    ordered = validate_writes(writes, protected, len(image))
    result = bytearray(image)
    for start, data in ordered:
        result[start:start + len(data)] = data
    candidate = bytes(result)
    extra = {r['storage']: r for r in components['extra_ui']['rows']}
    counts = {'stream_bindings': 0, 'fixed_names': 0}
    for binding, row in rows.items():
        storage, start, cap = int(row['pointer_storage'], 16), int(row['current_start'], 16), int(row['original_slot_bytes'])
        require(start == int(row['original_start'], 16), 'Relocated original start')
        require(candidate[storage:storage + 4] == image[storage:storage + 4] == (0x08000000 + start).to_bytes(4, 'little'), 'Pointer changed')
        if row['category'] == 'fixed_name':
            before = unpack_name(image[start:start + cap], (row['native_bytes'] - 1) // 3)
            actual = unpack_name(candidate[start:start + cap], (row['native_bytes'] - 1) // 3)
            counts['fixed_names'] += 1
        else:
            kind = 'full_text' if row['category'] == 'full_text' else 'compact'
            if storage in extra and not extra[storage]['existing_binding']:
                kind = 'extra'
            if kind == 'full_text':
                require(bounds.get(0x08000000 + start) == cap, 'Full bounds mismatch')
            selection = int(row['variant_selection'])
            args = (books[kind], 283 if kind == 'full_text' else 288, 1 if selection == 1 else 4, selection)
            before, _ = decode_parts(image[start:start + cap], *args, allow_suffix=True)
            actual, _ = decode_parts(candidate[start:start + cap], *args, allow_suffix=True)
            counts['stream_bindings'] += 1
        require(sha(before) == row['native_sha256'], 'Corpus native hash mismatch')
        expected = bytes.fromhex(changes[binding]['native_hex']) + b'\0' if binding in changes else before
        require(actual == expected, 'Full corpus readback mismatch: ' + binding)
    require(counts == {'stream_bindings': 10369, 'fixed_names': 2}, 'Readback count mismatch')
    require(all(candidate[a:b] == image[a:b] for a, b in protected), 'Protected bytes changed')
    require(sha(candidate) == TARGET, 'Accepted target mismatch')
    output_patch = create_bps(japanese, candidate)
    require(apply_bps(japanese, output_patch) == candidate, 'Cumulative patch reapplication mismatch')
    return candidate, output_patch, dict(counts, japanese_sha256=JP, baseline_sha256=BASE, target_sha256=sha(candidate), patch_sha256=sha(output_patch), changed_bindings=len(changes), changed_starts=len(writes), protected_segments=52, patch_reapplication=True, runtime_gameplay='NOT_RUN')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('japanese', *INPUTS, 'out'):
        parser.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), 'Output directory already exists')
    japanese = checked_read(args.japanese, JP)
    data = {name: checked_read(getattr(args, name), digest) for name, digest in INPUTS.items()}
    candidate, patch, report = rebuild(japanese, data.pop('baseline_patch'), **{k: json.loads(v) for k, v in data.items()})
    # Publish the complete directory only after every validation has passed.
    with tempfile.TemporaryDirectory(prefix='.v11a-', dir=args.out.parent) as temporary:
        stage = Path(temporary) / 'result'
        stage.mkdir()
        (stage / 'Xagros_Narikiri2_KOR_v1.1a.gba').write_bytes(candidate)
        (stage / 'Xagros_Narikiri2_KOR_v1.1a.bps').write_bytes(patch)
        (stage / 'BUILD_RESULT.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        require(not args.out.exists(), 'Output directory appeared during build')
        os.rename(stage, args.out)
    print(json.dumps(report))


if __name__ == '__main__':
    main()

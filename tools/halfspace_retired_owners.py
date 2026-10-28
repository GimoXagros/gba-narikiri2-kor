"""Named independently checked text suffixes; no general free-space scan."""
import hashlib
import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1]/'config/halfspace_retired_string_owners.json'
MANIFEST_SHA = 'ee3c4bdf35c59ae7ff4d45aab996d2774952bc3b2c412bb09f3f0868f6bde233'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest():
    raw=MANIFEST.read_bytes()
    if sha(raw)!=MANIFEST_SHA:
        raise ValueError('Reviewed retired-owner manifest changed')
    return json.loads(raw)


def check_preimages(image):
    """Require exact compressed prefixes, suffix bytes, pointers and decoder ABI."""
    if len(image)!=0x800000:
        raise ValueError('Original eight-MiB image required')
    spec=manifest()
    for row in spec['required_components']:
        at=row['new']
        if sha(image[at:at+row['size']])!=row['sha256']:
            raise ValueError('Retired-owner decoder/book prerequisite changed: '+row['name'])
    for row in spec['owners']:
        start,lo,hi=row['start'],row['reclaim_start'],row['reclaim_end']
        if sha(image[start:lo])!=row['prefix_sha256'] or sha(image[lo:hi])!=row['suffix_before_sha256']:
            raise ValueError('Retired-owner prefix or suffix changed: '+row['binding'])
        at=row['storage']
        if image[at:at+4]!=(0x08000000+start).to_bytes(4,'little'):
            raise ValueError('Retired-owner original text pointer changed')
    return spec['owners']


def checked_writes(writes):
    """Return only explicitly declared, nonoverlapping even Thumb allocations."""
    owners=manifest()['owners']
    accepted=[]
    for row in writes:
        lo,hi=row['start'],row['end']
        overlaps=[o for o in owners if max(lo,o['reclaim_start'])<min(hi,o['reclaim_end'])]
        if not overlaps:
            continue
        if len(overlaps)!=1 or lo&1 or hi&1 or not lo<hi:
            raise ValueError('Invalid retired-owner Thumb extent')
        owner=overlaps[0]
        if not owner['reclaim_start']<=lo<hi<=owner['reclaim_end']:
            raise ValueError('Retired-owner writer crosses protected prefix or end')
        if any(lo<b and a<hi for a,b in accepted):
            raise ValueError('Overlapping retired-owner writers')
        accepted.append((lo,hi))
    return accepted


def check_text_slots(before,after,corpus,writes):
    """All post-text changes require a declared, preimage-checked retired suffix."""
    spans=checked_writes(writes)
    if spans:
        check_preimages(before)
    if len(before)!=len(after) or len(after)!=0x800000:
        raise ValueError('Post-text ROM size changed')
    allowed=set(i for lo,hi in spans for i in range(lo,hi))
    for row in corpus['rows']:
        start=int(row['original_start'],16)
        end=start+row['original_slot_bytes']
        for at in range(start,end):
            if before[at]!=after[at] and at not in allowed:
                raise ValueError('Post-text stage changed live string bytes: '+row['binding_id'])
    for row in writes:
        if (row['start'],row['end']) in spans:
            lo,hi=row['start'],row['end']
            if sha(before[lo:hi])!=row['before_sha256'] or sha(after[lo:hi])!=row['after_sha256']:
                raise ValueError('Retired-owner writer hash mismatch')
    return spans

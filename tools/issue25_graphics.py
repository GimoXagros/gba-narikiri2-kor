"""Restore the five original AN9J battle labels requested for issue #25."""

from dataclasses import dataclass
from hashlib import sha256


ROM_SIZE = 0x800000
JAPANESE_SHA256 = 'a92c0f6dbb5c013b47b7178e23d81663e3952a10df7b1f68967ebf7bb3b98eb7'


@dataclass(frozen=True)
class Label:
    name: str
    start: int
    end: int
    v11c_sha256: str
    japanese_sha256: str


# The 4bpp tiles are stored uncompressed in their original sprite-piece order.
# Gald's rightmost OAM piece comes first in the ROM, so copy the stored span.
LABELS = (
    Label('Target', 0x6D63BC, 0x6D645C,
          '8f95962f7c718f75d5f8ecd525748d89e161a16b9dd17c3bc48c50198eaade6c',
          'f0232e427a94848c89f1f15bb2c02d31faf4688a3c4d8c8f47d1efce1422b5bf'),
    Label('Bonus', 0x6D6C3C, 0x6D6DBC,
          'ed2e031880a3c62e8c5145774b8fa77ad39b49abcaefdda0e0ac130174ba2df2',
          '3725b1661dc94941249f2ac2251c6af1c189d559e548e11a69cf9ac19f898b6a'),
    Label('Gald', 0x6D6DBC, 0x6D6EFC,
          'b62804c29a7239e90c315d08c60d83609daf0c52e1d9efa0caa3d4e3daf57780',
          'f6c7156de95158be7400aade2cc51c24d364241e741c16fa668ab4f24c44251b'),
    Label('EXP', 0x6D6EFC, 0x6D6FFC,
          '271d6dbe057722ccb78584ca17de38821ca86cb51837444f1a1df13ba6bdf5da',
          '05a771cc99c469e64c0728bea0283870fcb7ff9ba5e53cb8ff01b15c849407e1'),
    Label('HIT', 0x6D78BC, 0x6D79BC,
          '49087f91c66049e9c8d43346e3c804dd377f7346b2a0977eb2fe678df7a88391',
          '810972470d470f467617b701d81a04f629db807ec72869afcd89478b916408e5'),
)

# These JP frame records, pointers and OBJ palettes already appear in v1.1c.
LAYOUT_GUARDS = (
    ('Battle results frame pointer and OBJ palette', 0x2C8B0C, 0x2C8B30),
    ('Battle results OAM', 0x3AF47C, 0x3AF610),
    ('Battle status OBJ palette', 0x6D83BC, 0x6D83DC),
)


def restore_battle_graphics(japanese: bytes, baseline: bytes) -> tuple[bytes, list[dict]]:
    """Apply bounded label spans over v1.1c, allowing disjoint candidate edits."""
    if len(japanese) != ROM_SIZE or len(baseline) != ROM_SIZE:
        raise ValueError('Issue #25 battle graphics require two 8 MiB ROMs')
    if sha256(japanese).hexdigest() != JAPANESE_SHA256:
        raise ValueError('Issue #25 battle graphics require the exact Japanese AN9J ROM')
    for description, start, end in LAYOUT_GUARDS:
        if baseline[start:end] != japanese[start:end]:
            raise ValueError(f'Issue #25 {description} differs from Japanese AN9J')

    records = []
    result = bytearray(baseline)
    for label in LABELS:
        start, end = label.start, label.end
        before, original = baseline[start:end], japanese[start:end]
        if sha256(before).hexdigest() != label.v11c_sha256:
            raise ValueError(f'Issue #25 {label.name} differs from the expected v1.1c tiles')
        if sha256(original).hexdigest() != label.japanese_sha256:
            raise ValueError(f'Issue #25 {label.name} source tile span differs from its manifest')
        result[start:end] = original
        records.append(dict(
            id=f'issue25_battle_{label.name.lower()}', kind='raw_obj_tiles_4bpp',
            offset=start, end=end, size=end-start, before_sha256=label.v11c_sha256,
            after_sha256=sha256(result[start:end]).hexdigest(),
            changed_bytes=sum(old != new for old, new in zip(before, original, strict=True)),
        ))
    return bytes(result), records

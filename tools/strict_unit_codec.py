"""Experimental prefix codec for native glyph units at original text starts.

Each stream contains its own complete sequence of glyph/literal codes followed
by EOS and zero bits to the byte boundary. A shared tree contains only single
native glyphs or literal bytes, never complete multi-glyph sentences. No text
ID, pointer, per-entry output length or external full template is encoded.

Book: uint16 node count, uint16 zero, then count * 8-byte nodes. Internal
node = uint16 left/right index + four zero bytes. Leaf = 0x8000 | length,
uint16 zero, three raw glyph bytes plus zero padding. Length zero is EOS.
Bits are read MSB first. Unused bits in the last byte must be zero.
The caller must still prove the slot bound, book extent and output RAM lifetime.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import heapq
import struct
from types import MappingProxyType


def units(payload: bytes, kind: str) -> list[bytes]:
    if not isinstance(payload, bytes) or b'\0' in payload:
        raise ValueError('Native payload must exclude NUL')
    if kind not in ('compact', 'full_text'):
        raise ValueError('Unknown glyph representation')
    result, i = [], 0
    while i < len(payload):
        lead = payload[i]
        size = 1
        if kind == 'compact' and lead == 0x7f:
            if i+3 > len(payload) or not all(1 <= b <= 31 for b in payload[i+1:i+3]):
                raise ValueError('Truncated or invalid private glyph')
            size = 3
        elif kind == 'full_text' and (0x80 <= lead <= 0x9f or lead >= 0xe0):
            # This game's Wansung mapping is not standard CP932: 7F and
            # FD..FF are valid trail bytes. Match the actual native consumer.
            if i+1 == len(payload):
                raise ValueError('Truncated native double-byte glyph')
            size = 2
        result.append(payload[i:i+size])
        i += size
    return result


def build_book(payloads: list[bytes], kind: str, weights=None) -> bytes:
    if not payloads:
        raise ValueError('Empty glyph corpus')
    if weights is None:
        weights = [1] * len(payloads)
    if len(weights) != len(payloads) or any(type(w) is not int or w < 1 for w in weights):
        raise ValueError('Invalid positive corpus weights')
    freq = Counter()
    for raw, weight in zip(payloads, weights):
        for glyph in units(raw, kind) + [b'']:
            freq[glyph] += weight
    if len(freq) < 2:
        freq[b'\x01'] = 1  # keep EOS a bit code, including an all-empty corpus
    heap, serial = [], 0
    for glyph, count in sorted(freq.items()):
        heap.append((count, serial, glyph))
        serial += 1
    heapq.heapify(heap)
    while len(heap) > 1:
        a, b = heapq.heappop(heap), heapq.heappop(heap)
        heapq.heappush(heap, (a[0]+b[0], serial, (a[2], b[2])))
        serial += 1
    nodes = []
    def add(node):
        index = len(nodes)
        nodes.append(None)
        if isinstance(node, bytes):
            nodes[index] = struct.pack('<HH', 0x8000 | len(node), 0) + node.ljust(4, b'\0')
        else:
            left, right = add(node[0]), add(node[1])
            nodes[index] = struct.pack('<HHI', left, right, 0)
        return index
    add(heap[0][2])
    if len(nodes) >= 0x8000:
        raise ValueError('Tree exceeds node-index representation')
    return struct.pack('<HH', len(nodes), 0) + b''.join(nodes)


def fit_book(payloads: list[bytes], kind: str, capacities: list[int], max_attempts=64):
    """Fit a shared glyph tree, increasing frequency weights of overflowing rows.

    Weights affect the one shared tree only. No row-specific text, codebook,
    ID or weight array is needed by the runtime. A nonzero overflow result
    remains a failure; this optimizer does not invent extra slot capacity.
    """
    return fit_parts_book([[raw] for raw in payloads], kind, capacities, max_attempts)


def factor_variants(payloads: list[bytes], kind: str) -> list[bytes]:
    """Inline common prefix, left middle, right middle, common suffix.

    Both alternatives stay in the original slot. The runtime still needs a
    proven use-site selector; this factorization does not establish that hook.
    """
    if len(payloads) == 1:
        return payloads[:]
    if len(payloads) != 2 or payloads[0] == payloads[1]:
        raise ValueError('Expected one template or two distinct inline variants')
    a, b = (units(p, kind) for p in payloads)
    prefix = suffix = 0
    while prefix < min(len(a), len(b)) and a[prefix] == b[prefix]:
        prefix += 1
    while suffix < min(len(a), len(b))-prefix and a[-1-suffix] == b[-1-suffix]:
        suffix += 1
    ae, be = len(a)-suffix, len(b)-suffix
    return [b''.join(a[:prefix]), b''.join(a[prefix:ae]), b''.join(b[prefix:be]),
            b''.join(a[ae:])]


def fit_parts_book(groups: list[list[bytes]], kind: str, capacities: list[int], max_attempts=64):
    if len(groups) != len(capacities) or any(type(c) is not int or c < 1 for c in capacities):
        raise ValueError('Invalid slot capacities')
    if not 1 <= max_attempts <= 256:
        raise ValueError('Invalid optimization bound')
    if any(len(g) not in (1, 4) for g in groups):
        raise ValueError('Expected plain entry or four-part inline bundle')
    payloads, indices = [], []
    for group in groups:
        indices.append(list(range(len(payloads), len(payloads)+len(group))))
        payloads.extend(group)
    seqs = [units(raw, kind)+[b''] for raw in payloads]
    weights, trials, best = [1]*len(payloads), [], None
    for attempt in range(max_attempts):
        book = build_book(payloads, kind, weights)
        table = code_table(book)
        bits = [sum(table[g][1] for g in seq) for seq in seqs]
        sizes = [(sum(bits[i] for i in group)+7)//8 for group in indices]
        bad = [i for i, (size, cap) in enumerate(zip(sizes, capacities)) if size > cap]
        excess = sum(sizes[i]-capacities[i] for i in bad)
        key = (len(bad), excess, sum(sizes))
        trials.append(dict(attempt=attempt, overflow_count=len(bad), excess_bytes=excess,
                           encoded_occurrence_bytes=sum(sizes)))
        if best is None or key < best[0]:
            best = (key, book, sizes, weights[:])
        if not bad:
            break
        for i in bad:
            for j in indices[i]:
                weights[j] += max(1, weights[j]//2)
    return best[1], dict(trials=trials, best_overflow_count=best[0][0],
                        best_excess_bytes=best[0][1], encoded_occurrence_bytes=best[0][2],
                        encoded_sizes=best[2], training_weights=best[3])


@lru_cache(maxsize=8)
def code_table(book: bytes):
    if len(book) < 4:
        raise ValueError('Truncated codebook header')
    count, reserved = struct.unpack_from('<HH', book)
    if count < 3 or count >= 0x8000 or reserved or len(book) != 4+count*8:
        raise ValueError('Invalid codebook extent')
    seen, leaves, table = set(), set(), {}
    def visit(index, bits, width):
        if index >= count or index in seen or width > 31:
            raise ValueError('Invalid tree edge, cycle or excessive depth')
        seen.add(index)
        a, b = struct.unpack_from('<HH', book, 4+index*8)
        raw = book[8+index*8:12+index*8]
        if a & 0x8000:
            size = a & 0x7fff
            if size > 3 or b or any(raw[size:]) or 0 in raw[:size] or raw[:size] in leaves:
                raise ValueError('Invalid or duplicate glyph leaf')
            leaves.add(raw[:size])
            table[raw[:size]] = (bits, width)
        else:
            if any(raw):
                raise ValueError('Invalid internal node padding')
            visit(a, bits << 1, width+1)
            visit(b, (bits << 1)|1, width+1)
    visit(0, 0, 0)
    if len(seen) != count or b'' not in leaves:
        raise ValueError('Unreachable tree nodes or absent EOS')
    return MappingProxyType(table)


def encode(payload: bytes, kind: str, book: bytes) -> bytes:
    return encode_parts([payload], kind, book)


def encode_parts(parts: list[bytes], kind: str, book: bytes) -> bytes:
    if len(parts) not in (1, 4):
        raise ValueError('Expected plain entry or four-part inline bundle')
    table = code_table(book)
    value = width = 0
    for payload in parts:
        for glyph in units(payload, kind)+[b'']:
            bits, n = table[glyph]
            value = (value << n) | bits
            width += n
    padding = (-width) % 8
    return (value << padding).to_bytes((width+padding)//8, 'big')


def decode(stream: bytes, book: bytes, output_capacity: int, *, allow_suffix=False) -> tuple[bytes, int]:
    """Return native bytes and consumed bytes, bounded by the supplied slot.

    allow_suffix permits untouched original slot suffix bytes after the encoded
    stream. It never permits nonzero padding within the EOS byte.
    """
    return decode_parts(stream, book, output_capacity, 1, 1, allow_suffix=allow_suffix)


def decode_parts(stream: bytes, book: bytes, output_capacity: int,
                 part_count: int, selection: int, *, allow_suffix=False) -> tuple[bytes, int]:
    code_table(book)
    if part_count not in (1, 4) or not 0 < selection < 1 << part_count:
        raise ValueError('Invalid inline part selection')
    if output_capacity < 1:
        raise ValueError('Output capacity lacks NUL')
    result, index = bytearray(), 0
    for position in range(len(stream)*8):
        bit = (stream[position//8] >> (7-position%8)) & 1
        index = struct.unpack_from('<H', book, 4+index*8+bit*2)[0]
        a = struct.unpack_from('<H', book, 4+index*8)[0]
        if not a & 0x8000:
            continue
        size = a & 0x7fff
        if size == 0:
            part_count -= 1
            selection >>= 1
            if part_count:
                index = 0
                continue
            used = position//8+1
            if stream[used-1] & ((1 << (7-position%8))-1):
                raise ValueError('Nonzero EOS padding')
            if not allow_suffix and used != len(stream):
                raise ValueError('Trailing stream bytes')
            result.append(0)
            return bytes(result), used
        if selection & 1:
            if len(result)+size+1 > output_capacity:
                raise ValueError('Output capacity exceeded')
            result.extend(book[8+index*8:8+index*8+size])
        index = 0
    raise ValueError('Truncated stream or missing EOS')

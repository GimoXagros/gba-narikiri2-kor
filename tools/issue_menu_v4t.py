"""Use ARMv4T-defined additions in the copied compact tile scanner."""
from hashlib import sha256

SCAN_START = 0x34F11C
SCAN_SIZE = 100
SCAN_SHA256 = "391582842c924042023f23d1485467feafd29c68a620ffb15d23b117de49c4b7"
ADDS = (0x34F14C, 0x34F16A)


def fix_menu_scan(image):
    scan = image[SCAN_START:SCAN_START + SCAN_SIZE]
    if sha256(scan).hexdigest() != SCAN_SHA256:
        raise ValueError("Unexpected v1.1c menu scan loop")
    out = bytearray(image)
    records = []
    for offset in ADDS:
        # Format 5 ADD with two low registers is undefined on ARMv4T.
        # Format 2 ADDS computes the same address. Before the next branch
        # CMP or SUBS writes all condition flags used by that branch.
        before, after = bytes.fromhex("2344"), bytes.fromhex("1b19")
        if image[offset:offset + 2] != before:
            raise ValueError("Unexpected compact scan addition")
        out[offset:offset + 2] = after
        records.append(dict(owner="menu_scan_armv4t", offset=offset, end=offset + 2,
                            before_sha256=sha256(before).hexdigest(),
                            after_sha256=sha256(after).hexdigest()))
    return bytes(out), records

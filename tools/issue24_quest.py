"""Keep the original quest formatter's two fixed-width quote reads native."""
from hashlib import sha256

QUOTE_POINTER = 0x7F21A8
QUOTE_SLOT = 0x34D0D4
QUOTE_LITERAL = 0x9A860


def restore_quest_quotes(japanese, baseline):
    if len(japanese) != 0x800000 or len(baseline) != len(japanese):
        raise ValueError("Unexpected ROM size")
    pointer = (0x08000000 + QUOTE_SLOT).to_bytes(4, "little")
    if any(rom[QUOTE_POINTER:QUOTE_POINTER + 4] != pointer for rom in (japanese, baseline)):
        raise ValueError("Quest quote binding changed")
    native = japanese[QUOTE_SLOT:QUOTE_SLOT + 4]
    if native != "『』".encode("cp932") or baseline[QUOTE_SLOT:QUOTE_SLOT + 4] != bytes.fromhex("a4a51078"):
        raise ValueError("Unexpected quote encoding")
    # Replace LDR literal + pointer dereference with ADR + MOV r8,r8
    # (ARMv4T NOP). Both paths keep r0 and flags exactly as the native loops expect.
    spans = [(0x9A7D4, "22480068", bytes.fromhex("22a0c046")),
             (0x9A838, "09480068", bytes.fromhex("09a0c046")),
             (QUOTE_LITERAL, "a8217f08", native)]
    out = bytearray(baseline)
    records = []
    for address, expected, replacement in spans:
        before = bytes.fromhex(expected)
        if any(rom[address:address+4] != before for rom in (japanese, baseline)):
            raise ValueError(f"Quest machine code guard at {address:#x}")
        out[address:address+4] = replacement
        records.append(dict(owner="quest_quote_reader",offset=address,end=address+4,
                            before_sha256=sha256(before).hexdigest(),after_sha256=sha256(replacement).hexdigest()))
    return bytes(out), records

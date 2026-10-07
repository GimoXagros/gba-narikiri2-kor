"""Install tagged ARTE hooks in a guarded 13.27 MiB diagnostic-only ROM."""
from __future__ import annotations

import json
from pathlib import Path
import struct

from strict_runtime_arte_hook import patches, sha

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "private_validation/v11-runtime-worker/SELECT_JOB_DIAGNOSTIC_NOT_PRODUCT.gba"
OUTPUT = ROOT / "private_validation/v11-runtime-worker/ARTE_TAGGED_DIAGNOSTIC_NOT_PRODUCT.gba"
SOURCE_SHA = "a59eda54f47b8d39e390dcafcaa6c15091cea8d6d2ed47715f785e4b81a69d0f"
DATA_IMAGE = ROOT.parent / "narikiri2-v09d-graphics-test/private_validation/strict-layout-20261003/build-inline-native-a/TEXT_SLOT_IMAGE_NOT_PLAYABLE.bin"
DATA_SHA = "ba9a42690ce2899d9465a41cb326f31f4af6f4cc8047fcb4840f22e0ed3e5006"


def main():
    data = bytearray(SOURCE.read_bytes())
    if sha(data) != SOURCE_SHA or len(data) != 13_270_790:
        raise ValueError("Diagnostic source provenance changed")
    changes = []
    for offset, (before, after) in patches().items():
        if data[offset:offset + len(before)] != before or len(before) != len(after):
            raise ValueError(f"Ownership guard failed at {offset:08X}")
        data[offset:offset + len(after)] = after
        changes.append({"offset": f"0x{offset:08X}", "length": len(after),
                        "before_sha256": sha(before), "after_sha256": sha(after)})
    strict_image = DATA_IMAGE.read_bytes()
    if len(strict_image) != 0x800000 or sha(strict_image) != DATA_SHA:
        raise ValueError("ARTE compressed stream source provenance changed")
    offset = 0x002BCFE0
    before = bytes.fromhex("2568d7b2bcdedd")
    after = strict_image[offset:offset + 7]
    if data[offset:offset + 7] != before or after.hex() != "a55941ea1d89de":
        raise ValueError("ARTE strict source ownership guard failed")
    data[offset:offset + 7] = after
    changes.append({"offset": f"0x{offset:08X}", "length": 7,
                    "before_sha256": sha(before), "after_sha256": sha(after)})
    for storage, old in ((0x00375690, 0x08C0C364), (0x003756A4, 0x08C0C36E)):
        before = struct.pack("<I", old)
        after = struct.pack("<I", 0x082BCFE0)
        if data[storage:storage + 4] != before:
            raise ValueError(f"ARTE_{(storage-0x374A38)//20} table storage changed")
        data[storage:storage + 4] = after
        changes.append({"offset": f"0x{storage:08X}", "length": 4,
                        "before_sha256": sha(before), "after_sha256": sha(after)})
    OUTPUT.write_bytes(data)
    manifest = {"schema": "strict-runtime-arte-tagged-diagnostic-v1",
                "source_sha256": SOURCE_SHA, "output_sha256": sha(data),
                "output_size": len(data), "status": "DIAGNOSTIC_NOT_PRODUCT",
                "target_original_table_words_restored": True,
                "hooked_accessor": "08008C54", "hooked_formatter": "08002648",
                "accessor_tags": ["0A2BCFE0", "0C2BCFE0"],
                "strict_physical_stream": "082BCFE0", "changes": changes}
    OUTPUT.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()

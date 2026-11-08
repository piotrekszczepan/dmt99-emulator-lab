#!/usr/bin/env python3
"""Lock DMT-99 V2.4 to the Polish language and the code-rendered theme.

The public USB updater replaces the CH32 application but does not replace the
menu JPEGs in the external W25Q64.  On a physical meter, selecting another
language or Theme2 therefore exposes the stock Chinese/English/German assets.

This small follow-up patch wraps the stock language and layout accessors:

* every language read/write resolves to index 2 (the Polish code/resource slot),
* every layout read/write resolves to index 0 (the code-rendered Theme1).

The measurement code, calibration, thresholds and history are not changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from patch_dmt99_embedded_polish import LOAD, REG, branch, itype, jal, lui, pack


LANGUAGE_ACCESS = 0xD964
LANGUAGE_CONTINUE = 0xD968
LAYOUT_ACCESS = 0xDA04
LAYOUT_CONTINUE = 0xDA08
RESTORE_APPLY = 0xC290
RESTORE_CONTINUE = 0xC2B2

# The preceding Chinese-to-Polish payload ends at 0x1EC1C.  The remainder of
# its verified zero-filled V2.4 cave is large enough for these two 24-byte
# guards without moving or overwriting the earlier hooks.
LOCK_HOOK = 0x1EC1C
LOCK_HOOK_SIZE = 48


def encode_jal(pc: int, target: int, rd: int = 0) -> bytes:
    return int(jal(rd, target - pc)).to_bytes(4, "little")


def encode_addi(rd: int, rs1: int, immediate: int) -> bytes:
    return int(itype(0x13, rd, 0, rs1, immediate)).to_bytes(4, "little")


def build_forced_accessor(address: int, resume: int, forced: int) -> bytes:
    """Return a six-instruction guard for a stock packed-setting accessor."""
    pc = address
    words: list[int] = []

    def emit(word: int) -> None:
        nonlocal pc
        words.append(word)
        pc += 4

    # Read (a0 == 0): return the forced value without touching the setting.
    # Write: replace a1 with the forced value, replay the overwritten LUI a4,
    # then continue in the unmodified stock accessor.
    emit(branch(0, 10, REG["zero"], 16))             # beq a0,zero,read
    emit(itype(0x13, 11, 0, REG["zero"], forced))   # addi a1,zero,forced
    emit(lui(14, 0x20000))                           # stock: lui a4,0x20000
    emit(jal(REG["zero"], resume - pc))
    emit(itype(0x13, 10, 0, REG["zero"], forced))   # addi a0,zero,forced
    emit(itype(0x67, REG["zero"], 0, 1, 0))         # ret
    return pack(words)


def replace_exact(image: bytearray, address: int, old: bytes, new: bytes) -> None:
    if len(old) != len(new):
        raise ValueError("replacement length mismatch")
    offset = address - LOAD
    if image[offset:offset + len(old)] != old:
        raise SystemExit(f"Unexpected bytes at 0x{address:08X}; refusing to patch")
    image[offset:offset + len(new)] = new


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    source = args.source.read_bytes()
    image = bytearray(source)
    hook_offset = LOCK_HOOK - LOAD
    if any(image[hook_offset:hook_offset + LOCK_HOOK_SIZE]):
        raise SystemExit("Polish-lock cave is not empty; refusing to patch")

    language_guard = build_forced_accessor(LOCK_HOOK, LANGUAGE_CONTINUE, 2)
    layout_guard_address = LOCK_HOOK + len(language_guard)
    layout_guard = build_forced_accessor(layout_guard_address, LAYOUT_CONTINUE, 0)
    payload = language_guard + layout_guard
    if len(payload) != LOCK_HOOK_SIZE:
        raise SystemExit(f"Unexpected lock payload size: {len(payload)}")

    stock_lui = int(lui(14, 0x20000)).to_bytes(4, "little")
    replace_exact(image, LANGUAGE_ACCESS, stock_lui,
                  encode_jal(LANGUAGE_ACCESS, LOCK_HOOK))
    replace_exact(image, LAYOUT_ACCESS, stock_lui,
                  encode_jal(LAYOUT_ACCESS, layout_guard_address))

    # The earlier Polish image restored the user's complete saved language.
    # Replace that 28-byte restore block with explicit Polish + Theme1 writes,
    # so a meter currently left in English or Theme2 recovers on first boot.
    old_restore = b"".join((
        encode_addi(11, 0, 0),
        encode_addi(10, 0, 0),
        encode_jal(RESTORE_APPLY + 8, LANGUAGE_ACCESS, 1),
        encode_addi(11, 10, 0),
        encode_addi(10, 0, 1),
        encode_jal(RESTORE_APPLY + 20, LANGUAGE_ACCESS, 1),
        encode_jal(RESTORE_APPLY + 24, RESTORE_CONTINUE, 0),
    ))
    new_restore = b"".join((
        encode_addi(11, 0, 2),
        encode_addi(10, 0, 1),
        encode_jal(RESTORE_APPLY + 8, LANGUAGE_ACCESS, 1),
        encode_addi(11, 0, 0),
        encode_addi(10, 0, 1),
        encode_jal(RESTORE_APPLY + 20, LAYOUT_ACCESS, 1),
        encode_jal(RESTORE_APPLY + 24, RESTORE_CONTINUE, 0),
    ))
    replace_exact(image, RESTORE_APPLY, old_restore, new_restore)
    image[hook_offset:hook_offset + len(payload)] = payload

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    report = {
        "definition": "Polish-only lock; language index 2 and Theme1/layout 0",
        "source": str(args.source),
        "output": str(args.output),
        "size": len(image),
        "source_sha256": hashlib.sha256(source).hexdigest().upper(),
        "output_sha256": hashlib.sha256(image).hexdigest().upper(),
        "language_guard": hex(LOCK_HOOK),
        "layout_guard": hex(layout_guard_address),
        "payload_bytes": len(payload),
        "scope": [
            "settings_language_access",
            "settings_layout_access",
            "startup settings apply",
            "verified zero-filled code cave",
        ],
    }
    manifest = args.manifest or args.output.with_suffix(".json")
    manifest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

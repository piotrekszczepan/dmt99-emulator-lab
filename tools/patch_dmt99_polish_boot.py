#!/usr/bin/env python3
"""Prepare stock DMT-99 V2.4 language restore for the Polish patch chain."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


LOAD = 0x6400
RESET_LANGUAGE = 0x15168
LANGUAGE_ACCESS = 0xD964
RESTORE_APPLY = 0xC290
RESTORE_CONTINUE = 0xC2B2


def jal(pc: int, target: int, rd: int = 0) -> bytes:
    immediate = target - pc
    if immediate & 1 or not -(1 << 20) <= immediate < (1 << 20):
        raise ValueError(f"invalid JAL displacement: {immediate}")
    value = immediate & 0x1FFFFF
    word = (((value >> 20) & 1) << 31) | (((value >> 1) & 0x3FF) << 21)
    word |= (((value >> 11) & 1) << 20) | (((value >> 12) & 0xFF) << 12)
    word |= (rd & 0x1F) << 7 | 0x6F
    return struct.pack("<I", word)


def addi(rd: int, rs1: int, immediate: int) -> bytes:
    word = ((immediate & 0xFFF) << 20) | (rs1 << 15) | (rd << 7) | 0x13
    return struct.pack("<I", word)


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
    reset_stub = addi(11, 0, 2) + addi(10, 0, 1) + jal(RESET_LANGUAGE + 8, LANGUAGE_ACCESS)
    replace_exact(
        image,
        RESET_LANGUAGE,
        bytes.fromhex("EF 12 EF CA 01 45 EF 30 CF DF 37 55"),
        reset_stub,
    )

    restore_stub = b"".join((
        addi(11, 0, 0),
        addi(10, 0, 0),
        jal(RESTORE_APPLY + 8, LANGUAGE_ACCESS, 1),
        addi(11, 10, 0),
        addi(10, 0, 1),
        jal(RESTORE_APPLY + 20, LANGUAGE_ACCESS, 1),
        jal(RESTORE_APPLY + 24, RESTORE_CONTINUE),
    ))
    replace_exact(
        image,
        RESTORE_APPLY,
        bytes.fromhex(
            "81 45 01 45 EF 10 00 6D B7 45 02 00 39 ED 37 46 02 00 "
            "13 06 06 C3 13 85 81 8E 93 85"
        ),
        restore_stub,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    report = {
        "definition": "language index 2 after reset and full language restore on boot",
        "source": str(args.source),
        "output": str(args.output),
        "size": len(image),
        "source_sha256": hashlib.sha256(source).hexdigest().upper(),
        "output_sha256": hashlib.sha256(image).hexdigest().upper(),
        "reset_language_address": hex(RESET_LANGUAGE),
        "restore_address": hex(RESTORE_APPLY),
    }
    manifest = args.manifest or args.output.with_suffix(".json")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

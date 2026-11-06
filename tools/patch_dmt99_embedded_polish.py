#!/usr/bin/env python3
"""Add a language-index-2-only Polish ASCII translation hook to DMT-99 V2.4."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

LOAD = 0x6400
ASCII_RENDER = 0x8588
ASCII_RENDER_CONTINUE = 0x858C
REGISTER_SAVE_HELPER = 0x6608
HOOK = 0x1EAB0
CAVE_SIZE = 513

# These are firmware-ROM strings used by the compact main menu.  The hook is
# active only while the stored language index equals 2 (the German slot).
TRANSLATIONS = [
    (0x2541C, "Wybor trybu"),
    (0x25210, "Progi"),
    (0x2542C, "ustawienia"),
    (0x25438, "Historia"),
    (0x25448, "Ustawienia"),
    (0x249F4, "Resetuj"),
    (0x25458, "Informacje"),
    (0x253A4, "Normalny"),
    (0x253AC, "Rejestr"),
    (0x25160, "Pomiary"),
]

REG = {"zero": 0, "t0": 5, "t1": 6, "a2": 12}


def lui(rd: int, imm20: int) -> int:
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | 0x37


def itype(opcode: int, rd: int, funct3: int, rs1: int, imm: int) -> int:
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def branch(funct3: int, rs1: int, rs2: int, offset: int) -> int:
    if offset & 1 or not -4096 <= offset <= 4094:
        raise ValueError(f"invalid branch offset {offset}")
    value = offset & 0x1FFF
    return (((value >> 12) & 1) << 31) | (((value >> 5) & 0x3F) << 25) | \
           (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | \
           (((value >> 1) & 0xF) << 8) | (((value >> 11) & 1) << 7) | 0x63


def jal(rd: int, offset: int) -> int:
    if offset & 1 or not -(1 << 20) <= offset < (1 << 20):
        raise ValueError(f"invalid JAL offset {offset}")
    value = offset & 0x1FFFFF
    return (((value >> 20) & 1) << 31) | (((value >> 1) & 0x3FF) << 21) | \
           (((value >> 11) & 1) << 20) | (((value >> 12) & 0xFF) << 12) | \
           (rd << 7) | 0x6F


def split_address(address: int) -> tuple[int, int]:
    high = (address + 0x800) >> 12
    low = address - (high << 12)
    return high, low


def pack(words: list[int]) -> bytes:
    return b"".join(struct.pack("<I", word) for word in words)


def build_hook() -> tuple[bytes, list[dict]]:
    code_size = 15 * 4
    table_address = HOOK + code_size
    string_address = table_address + (len(TRANSLATIONS) + 1) * 8

    strings = bytearray()
    table = bytearray()
    manifest = []
    for original, translated in TRANSLATIONS:
        target = string_address + len(strings)
        encoded = translated.encode("ascii") + b"\0"
        table += struct.pack("<II", original, target)
        strings += encoded
        manifest.append({"original_address": hex(original), "polish": translated,
                         "polish_address": hex(target)})
    table += b"\0" * 8

    table_hi, table_lo = split_address(table_address)
    pc = HOOK
    words: list[int] = []

    def emit(word: int) -> None:
        nonlocal pc
        words.append(word); pc += 4

    # Read the low three language bits from settings at SRAM 0x2000003e.
    emit(lui(REG["t0"], 0x20000))
    emit(itype(0x03, REG["t0"], 5, REG["t0"], 0x3E))       # lhu t0,0x3e(t0)
    emit(itype(0x13, REG["t0"], 7, REG["t0"], 7))          # andi t0,t0,7
    emit(itype(0x13, REG["t1"], 0, REG["zero"], 2))        # li t1,2
    original_pc = HOOK + 52
    emit(branch(1, REG["t0"], REG["t1"], original_pc - pc)) # bne
    emit(lui(REG["t0"], table_hi))
    emit(itype(0x13, REG["t0"], 0, REG["t0"], table_lo))
    loop_pc = pc
    emit(itype(0x03, REG["t1"], 2, REG["t0"], 0))          # lw t1,0(t0)
    emit(branch(0, REG["t1"], REG["zero"], original_pc - pc))
    found_pc = HOOK + 48
    emit(branch(0, REG["a2"], REG["t1"], found_pc - pc))
    emit(itype(0x13, REG["t0"], 0, REG["t0"], 8))
    emit(jal(REG["zero"], loop_pc - pc))
    emit(itype(0x03, REG["a2"], 2, REG["t0"], 4))          # found: lw a2,4(t0)
    emit(jal(REG["t0"], REGISTER_SAVE_HELPER - pc))
    emit(jal(REG["zero"], ASCII_RENDER_CONTINUE - pc))

    payload = pack(words) + table + strings
    if len(payload) > CAVE_SIZE:
        raise ValueError(f"hook needs {len(payload)} bytes, cave has {CAVE_SIZE}")
    return payload, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    image = bytearray(args.source.read_bytes())
    entry = ASCII_RENDER - LOAD
    cave = HOOK - LOAD
    if image[entry:entry + 4] != bytes.fromhex("efe20f88"):
        raise SystemExit("Unexpected V2.4 ASCII renderer entry; refusing to patch")
    if any(image[cave:cave + CAVE_SIZE]):
        raise SystemExit("Selected V2.4 code cave is not empty; refusing to patch")

    payload, mappings = build_hook()
    image[entry:entry + 4] = struct.pack("<I", jal(REG["zero"], HOOK - ASCII_RENDER))
    image[cave:cave + len(payload)] = payload
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)

    report = {
        "definition": "language-index-2-only embedded ASCII Polish hook",
        "source": str(args.source), "output": str(args.output),
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest().upper(),
        "output_sha256": hashlib.sha256(image).hexdigest().upper(),
        "renderer_entry": hex(ASCII_RENDER), "hook_address": hex(HOOK),
        "hook_bytes": len(payload), "mappings": mappings,
    }
    if args.manifest:
        args.manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

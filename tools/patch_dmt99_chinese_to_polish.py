#!/usr/bin/env python3
"""Make the visible Chinese choice select the Polish (German-resource) slot.

The DMT-99 V2.4 settings screen exposes only Chinese and English, although the
firmware contains six resource prefixes.  This patch keeps English at index 1,
renders the first choice as ``Polski`` and stores index 2 for that choice.  The
Polish JPEG set therefore remains isolated in ``MENU/GERMAN`` while the user
sees only Polski/English.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from patch_dmt99_embedded_polish import (
    LOAD, ASCII_RENDER, ASCII_RENDER_CONTINUE, REGISTER_SAVE_HELPER,
    REG, branch, itype, jal, lui, pack, split_address,
)

CHINESE_RENDER = 0x8E46
CHINESE_RENDER_CONTINUE = 0x8E4A
HOOK = 0x1EAB0
HOOK_SIZE = 513
STRING_CAVES = (
    (0x27210, 224),
    (0x2731C, 101),
)

# ASCII strings used by the compact menu and settings pages.  The hook is
# active only for stored language index 2, so English at index 1 is untouched.
ASCII_TRANSLATIONS = [
    (0x2541C, "Wybor trybu"),
    (0x25210, "Ustawienia"),
    (0x2542C, "progow"),
    (0x25438, "Historia"),
    (0x25448, "Ustawienia"),
    (0x249F4, "Resetuj"),
    (0x25458, "O mierniku"),
    (0x253A4, "Normalny"),
    (0x253AC, "Rejestr"),
    (0x25158, "Tryb"),
    (0x25160, "Pomiar"),
    (0x247D4, "Jasnosc"),
    (0x247E0, "Jedn. temp."),
    (0x247F4, "Jasnosc:"),
    (0x24800, "Jedn. temp.:") ,
    (0x24F38, "Resetuj"),
    (0x24F40, "Powrot"),
    (0x24F6C, "Auto wylaczanie"),
    (0x24F7C, "Auto wylaczanie:"),
    (0x25080, "Motyw1"),
    (0x25090, "Motyw2"),
    (0x250D4, "Motyw"),
    (0x250DC, "Jezyk"),
    (0x250E8, "Motyw:"),
    (0x250F0, "Jezyk:"),
    (0x2494C, "Napiecie:"),
    (0x24958, "Prad:"),
    (0x24964, "Temperatura:"),
]

# The theme/language screen uses three Chinese glyph strings.  Its language
# read is locally mapped from index 2 to the first-row layout, then these glyph
# calls are redirected to the ASCII renderer.
CHINESE_TRANSLATIONS = [
    (0x25078, "Motyw"),
    (0x25098, "Polski"),
    (0x250CC, "Jezyk"),
]


def align4(value: int) -> int:
    return (value + 3) & ~3


def encode_jal(pc: int, target: int, rd: int = 0) -> bytes:
    return struct.pack("<I", jal(rd, target - pc))


def build_string_pools() -> tuple[list[tuple[int, bytes]], dict[str, int]]:
    pools = [(address, bytearray()) for address, _ in STRING_CAVES]
    addresses: dict[str, int] = {}
    for _, text in ASCII_TRANSLATIONS + CHINESE_TRANSLATIONS:
        if text in addresses:
            continue
        encoded = text.encode("ascii") + b"\0"
        for index, ((base, size), (_, pool)) in enumerate(zip(STRING_CAVES, pools)):
            if len(pool) + len(encoded) <= size:
                addresses[text] = base + len(pool)
                pool += encoded
                break
        else:
            capacity = sum(size for _, size in STRING_CAVES)
            raise ValueError(f"string pools cannot fit {text!r}; total capacity {capacity} bytes")
    return [(base, bytes(pool)) for base, pool in pools], addresses


def make_table(items, addresses) -> bytes:
    data = bytearray()
    for original, text in items:
        data += struct.pack("<II", original, addresses[text])
    data += b"\0" * 8
    return bytes(data)


def build_ascii_hook(table_address: int) -> bytes:
    table_hi, table_lo = split_address(table_address)
    pc = HOOK
    words: list[int] = []

    def emit(word: int) -> None:
        nonlocal pc
        words.append(word)
        pc += 4

    # Translate only the hidden index-2 resource slot used for Polish.
    emit(lui(REG["t0"], 0x20000))
    emit(itype(0x03, REG["t0"], 5, REG["t0"], 0x3E))
    emit(itype(0x13, REG["t0"], 7, REG["t0"], 7))
    emit(itype(0x13, REG["t1"], 0, REG["zero"], 2))
    original_pc = HOOK + 52
    emit(branch(1, REG["t0"], REG["t1"], original_pc - pc))
    emit(lui(REG["t0"], table_hi))
    emit(itype(0x13, REG["t0"], 0, REG["t0"], table_lo))
    loop_pc = pc
    emit(itype(0x03, REG["t1"], 2, REG["t0"], 0))
    emit(branch(0, REG["t1"], REG["zero"], original_pc - pc))
    found_pc = HOOK + 48
    emit(branch(0, REG["a2"], REG["t1"], found_pc - pc))
    emit(itype(0x13, REG["t0"], 0, REG["t0"], 8))
    emit(jal(REG["zero"], loop_pc - pc))
    emit(itype(0x03, REG["a2"], 2, REG["t0"], 4))
    emit(jal(REG["t0"], REGISTER_SAVE_HELPER - pc))
    emit(jal(REG["zero"], ASCII_RENDER_CONTINUE - pc))
    return pack(words)


def build_chinese_hook(address: int, table_address: int) -> bytes:
    table_hi, table_lo = split_address(table_address)
    pc = address
    words: list[int] = []

    def emit(word: int) -> None:
        nonlocal pc
        words.append(word)
        pc += 4

    emit(lui(REG["t0"], table_hi))
    emit(itype(0x13, REG["t0"], 0, REG["t0"], table_lo))
    loop_pc = pc
    emit(itype(0x03, REG["t1"], 2, REG["t0"], 0))
    original_pc = address + 36
    found_pc = address + 28
    emit(branch(0, REG["t1"], REG["zero"], original_pc - pc))
    emit(branch(0, REG["a2"], REG["t1"], found_pc - pc))
    emit(itype(0x13, REG["t0"], 0, REG["t0"], 8))
    emit(jal(REG["zero"], loop_pc - pc))
    emit(itype(0x03, REG["a2"], 2, REG["t0"], 4))
    emit(jal(REG["zero"], ASCII_RENDER - pc))
    emit(jal(REG["t0"], REGISTER_SAVE_HELPER - pc))
    emit(jal(REG["zero"], CHINESE_RENDER_CONTINUE - pc))
    return pack(words)


def build_theme_language_reader(address: int) -> bytes:
    pc = address
    words = [
        lui(REG["t0"], 0x20000),
        itype(0x03, 10, 5, REG["t0"], 0x3E),       # lhu a0,0x3e(t0)
        itype(0x13, 10, 7, 10, 7),                 # andi a0,a0,7
        itype(0x13, REG["t0"], 0, REG["zero"], 2),
        branch(1, 10, REG["t0"], 8),              # index != 2: return as-is
        itype(0x13, 10, 0, REG["zero"], 0),        # index 2: first row
        itype(0x67, REG["zero"], 0, 1, 0),         # ret
    ]
    return pack(words)


def build_payload() -> tuple[bytes, list[tuple[int, bytes]], dict]:
    pools, addresses = build_string_pools()
    ascii_code_size = 15 * 4
    ascii_table_address = HOOK + ascii_code_size
    ascii_table = make_table(ASCII_TRANSLATIONS, addresses)
    chinese_hook_address = align4(ascii_table_address + len(ascii_table))
    chinese_code_size = 11 * 4
    chinese_table_address = chinese_hook_address + chinese_code_size
    chinese_table = make_table(CHINESE_TRANSLATIONS, addresses)
    theme_reader_address = align4(chinese_table_address + len(chinese_table))

    chunks = [
        (HOOK, build_ascii_hook(ascii_table_address)),
        (ascii_table_address, ascii_table),
        (chinese_hook_address, build_chinese_hook(chinese_hook_address, chinese_table_address)),
        (chinese_table_address, chinese_table),
        (theme_reader_address, build_theme_language_reader(theme_reader_address)),
    ]
    end = max(address + len(data) for address, data in chunks)
    if end - HOOK > HOOK_SIZE:
        raise ValueError(f"hook payload needs {end - HOOK} bytes, cave has {HOOK_SIZE}")
    payload = bytearray(end - HOOK)
    for address, data in chunks:
        payload[address - HOOK:address - HOOK + len(data)] = data
    meta = {
        "hook_address": hex(HOOK),
        "hook_bytes": len(payload),
        "string_caves": [
            {"address": hex(address), "bytes": len(pool)}
            for address, pool in pools
        ],
        "string_bytes": sum(len(pool) for _, pool in pools),
        "chinese_hook_address": hex(chinese_hook_address),
        "theme_reader_address": hex(theme_reader_address),
    }
    return bytes(payload), pools, meta


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
    payload, string_pools, meta = build_payload()

    if any(image[HOOK - LOAD:HOOK - LOAD + HOOK_SIZE]):
        raise SystemExit("Primary V2.4 code cave is not empty; refusing to patch")
    for address, size in STRING_CAVES:
        if any(image[address - LOAD:address - LOAD + size]):
            raise SystemExit(f"V2.4 string cave at 0x{address:X} is not empty; refusing to patch")
    replace_exact(image, ASCII_RENDER, bytes.fromhex("efe20f88"), encode_jal(ASCII_RENDER, HOOK))

    # Addresses are known only after the tables have been laid out.
    chinese_hook = int(meta["chinese_hook_address"], 16)
    theme_reader = int(meta["theme_reader_address"], 16)
    replace_exact(image, CHINESE_RENDER, bytes.fromhex("efd22ffc"),
                  encode_jal(CHINESE_RENDER, chinese_hook))
    for call_site in (0x15F2E, 0x160BA):
        replace_exact(image, call_site, encode_jal(call_site, 0xD964, 1),
                      encode_jal(call_site, theme_reader, 1))

    # Both classic and compact language-selection renderers: the first visible
    # choice writes index 2 (Polish resources), while the second keeps index 1.
    for address in (0x1377C, 0x13E08):
        replace_exact(image, address, bytes.fromhex("8145"), bytes.fromhex("8945"))

    # The first-boot selector reuses the Polish German-slot label images.
    replace_exact(image, 0x24F10, b"menu/chinese.jpg\0", b"menu/german.jpg\0\0")
    replace_exact(image, 0x24F8C, b"menu/chinese_.jpg\0", b"menu/german_.jpg\0\0")

    image[HOOK - LOAD:HOOK - LOAD + len(payload)] = payload
    for address, string_pool in string_pools:
        image[address - LOAD:address - LOAD + len(string_pool)] = string_pool
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)

    report = {
        "definition": "visible Chinese choice replaced by Polish; English preserved",
        "source": str(args.source),
        "output": str(args.output),
        "source_sha256": hashlib.sha256(source).hexdigest().upper(),
        "output_sha256": hashlib.sha256(image).hexdigest().upper(),
        **meta,
        "visible_choices": ["Polski", "English"],
        "stored_indices": {"Polski": 2, "English": 1},
        "resource_prefixes": {"Polski": "menu/german/", "English": "menu/english/"},
        "ascii_mappings": [{"address": hex(a), "text": t} for a, t in ASCII_TRANSLATIONS],
        "glyph_mappings": [{"address": hex(a), "text": t} for a, t in CHINESE_TRANSLATIONS],
    }
    if args.manifest:
        args.manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

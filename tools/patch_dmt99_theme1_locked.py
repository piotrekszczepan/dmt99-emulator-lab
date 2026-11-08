#!/usr/bin/env python3
"""Keep DMT-99 V2.4 Theme1 while preserving Polish and English languages.

Input is the stage that exposes Polish as the first choice (index 2) and
English as the second choice (index 1).  Only the packed layout accessor is
wrapped: reads return Theme1 and writes store Theme1.  Measurement rendering,
mode images and the language accessor are not modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from patch_dmt99_embedded_polish import LOAD, REG, branch, itype, jal, lui, pack


LAYOUT_ACCESS = 0xDA04
LAYOUT_CONTINUE = 0xDA08
THEME_GUARD = 0x1EC1C
THEME_GUARD_SIZE = 24


def encode_jal(pc: int, target: int, rd: int = 0) -> bytes:
    return int(jal(rd, target - pc)).to_bytes(4, "little")


def build_forced_theme1() -> bytes:
    pc = THEME_GUARD
    words: list[int] = []

    def emit(word: int) -> None:
        nonlocal pc
        words.append(word)
        pc += 4

    emit(branch(0, 10, REG["zero"], 16))            # read when a0 == 0
    emit(itype(0x13, 11, 0, REG["zero"], 0))       # writes always store layout 0
    emit(lui(14, 0x20000))                           # overwritten stock instruction
    emit(jal(REG["zero"], LAYOUT_CONTINUE - pc))
    emit(itype(0x13, 10, 0, REG["zero"], 0))       # reads always return layout 0
    emit(itype(0x67, REG["zero"], 0, 1, 0))         # ret
    return pack(words)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    source = args.source.read_bytes()
    image = bytearray(source)
    cave = THEME_GUARD - LOAD
    if any(image[cave:cave + THEME_GUARD_SIZE]):
        raise SystemExit("Theme1 guard cave is not empty; refusing to patch")

    stock_lui = int(lui(14, 0x20000)).to_bytes(4, "little")
    offset = LAYOUT_ACCESS - LOAD
    if image[offset:offset + 4] != stock_lui:
        raise SystemExit("Unexpected layout accessor; refusing to patch")
    image[offset:offset + 4] = encode_jal(LAYOUT_ACCESS, THEME_GUARD)
    payload = build_forced_theme1()
    image[cave:cave + len(payload)] = payload

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    report = {
        "definition": "Polish default, English second, stock measurement symbols, Theme1 only",
        "source": str(args.source),
        "output": str(args.output),
        "size": len(image),
        "source_sha256": hashlib.sha256(source).hexdigest().upper(),
        "output_sha256": hashlib.sha256(image).hexdigest().upper(),
        "layout_accessor": hex(LAYOUT_ACCESS),
        "theme_guard": hex(THEME_GUARD),
        "payload_bytes": len(payload),
        "measurement_rendering_modified": False,
        "language_accessor_modified": False,
    }
    manifest = args.manifest or args.output.with_suffix(".json")
    manifest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

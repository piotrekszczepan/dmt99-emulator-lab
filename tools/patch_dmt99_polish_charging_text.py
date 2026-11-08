#!/usr/bin/env python3
"""Replace the German charging JPEG caption with Polish ASCII text.

Input is the validated Polish/English Theme1 image.  The stock warning and
plug artwork stays untouched.  Only the language-specific JPEG draw call is
redirected: English still draws its stock JPEG, while language index 2 draws
four short Polish ASCII lines with the firmware's existing text renderer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from patch_dmt99_embedded_polish import (
    LOAD, ASCII_RENDER, REG, branch, itype, jal, lui, pack, split_address,
)

CHARGE_IMAGE_CALL = 0x14D2E
IMAGE_RENDER = 0x678C
CHARGE_CONTINUE = 0x14D32
HOOK = 0x205FC
HOOK_SIZE = 88
TABLE = 0x1EC64
TABLE_SIZE = 40
STRING_CAVE = 0x27336
STRING_CAVE_SIZE = 75
LINES = ((88, 87, "Nie uzywaj podczas"), (124, 103, "ladowania."),
         (80, 123, "Przed pomiarem odlacz"), (120, 139, "ladowarke."))

def encode_jal(pc: int, target: int, rd: int = 0) -> bytes:
    return struct.pack("<I", jal(rd, target - pc))

def build_strings() -> tuple[bytes, dict[str, int]]:
    data = bytearray(); addresses: dict[str, int] = {}
    for _, _, text in LINES:
        addresses[text] = STRING_CAVE + len(data); data += text.encode("ascii") + b"\0"
    if len(data) > STRING_CAVE_SIZE: raise ValueError("charging string cave is too small")
    return bytes(data), addresses

def build_table(addresses: dict[str, int]) -> bytes:
    data = bytearray()
    for x, y, text in LINES: data += struct.pack("<HHI", x, y, addresses[text])
    data += b"\0" * 8
    if len(data) != TABLE_SIZE: raise AssertionError("unexpected charging table size")
    return bytes(data)

def build_hook() -> bytes:
    table_hi, table_lo = split_address(TABLE); pc = HOOK; words: list[int] = []
    def emit(word: int) -> None:
        nonlocal pc; words.append(word); pc += 4
    emit(lui(REG["t0"], 0x20000)); emit(itype(0x03, REG["t0"], 5, REG["t0"], 0x3E))
    emit(itype(0x13, REG["t0"], 7, REG["t0"], 7)); emit(itype(0x13, REG["t1"], 0, REG["zero"], 2))
    non_polish = HOOK + 80; emit(branch(1, REG["t0"], REG["t1"], non_polish - pc))
    emit(lui(18, table_hi)); emit(itype(0x13, 18, 0, 18, table_lo)); emit(itype(0x13, 19, 0, REG["zero"], -0x800))
    loop = pc
    emit(itype(0x03, 10, 5, 18, 0)); emit(itype(0x03, 11, 5, 18, 2)); emit(itype(0x03, 12, 2, 18, 4))
    emit(itype(0x13, 13, 0, 19, 0)); emit(itype(0x13, 14, 0, 19, 0)); emit(itype(0x13, 15, 0, REG["zero"], 16))
    emit(itype(0x13, 16, 0, REG["zero"], 1)); emit(jal(1, ASCII_RENDER - pc)); emit(itype(0x13, 18, 0, 18, 8))
    emit(itype(0x03, REG["t1"], 5, 18, 0)); emit(branch(1, REG["t1"], REG["zero"], loop - pc))
    emit(jal(REG["zero"], CHARGE_CONTINUE - pc)); emit(jal(1, IMAGE_RENDER - pc)); emit(jal(REG["zero"], CHARGE_CONTINUE - pc))
    code = pack(words)
    if len(code) != HOOK_SIZE: raise AssertionError("unexpected charging hook size")
    return code

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("source",type=Path); p.add_argument("output",type=Path); p.add_argument("--manifest",type=Path); a=p.parse_args()
    source=a.source.read_bytes(); image=bytearray(source)
    for address,size,label in ((HOOK,HOOK_SIZE,"hook"),(TABLE,TABLE_SIZE,"table"),(STRING_CAVE,STRING_CAVE_SIZE,"strings")):
        if any(image[address-LOAD:address-LOAD+size]): raise SystemExit(f"{label} cave is not empty")
    off=CHARGE_IMAGE_CALL-LOAD; stock=encode_jal(CHARGE_IMAGE_CALL,IMAGE_RENDER,1)
    if image[off:off+4] != stock: raise SystemExit("unexpected charging image call")
    strings,addresses=build_strings(); table=build_table(addresses); hook=build_hook()
    image[off:off+4]=encode_jal(CHARGE_IMAGE_CALL,HOOK); image[HOOK-LOAD:HOOK-LOAD+len(hook)]=hook
    image[TABLE-LOAD:TABLE-LOAD+len(table)]=table; image[STRING_CAVE-LOAD:STRING_CAVE-LOAD+len(strings)]=strings
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_bytes(image)
    report={"definition":"Polish charging text; stock warning artwork; English JPEG preserved","source":str(a.source),"output":str(a.output),"size":len(image),"source_sha256":hashlib.sha256(source).hexdigest().upper(),"output_sha256":hashlib.sha256(image).hexdigest().upper(),"charging_call":hex(CHARGE_IMAGE_CALL),"hook":hex(HOOK),"table":hex(TABLE),"string_cave":hex(STRING_CAVE),"lines":[{"x":x,"y":y,"text":text} for x,y,text in LINES],"measurement_rendering_modified":False,"w25q64_modified":False}
    manifest=a.manifest or a.output.with_suffix(".json"); manifest.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__ == "__main__": main()

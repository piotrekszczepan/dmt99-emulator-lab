#!/usr/bin/env python3
"""Replace regular-view mode symbols with Polish ASCII measurement names.

The stock Theme1 draws large JPEG mode symbols such as ``V~``.  This patch
redirects only the regular-view mode-image call sites to the firmware's own
ASCII renderer.  Unit images beside the numeric value, measurement handling,
calibration and the NCV/LIVE screens remain unchanged.
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


DRAW_HOOK = 0x1EC4C
DRAW_HOOK_LIMIT = 0x1ECB1
NOOP_HOOK = 0x205FC
CLEAR_HOOK = 0x2062C
TABLE = 0x207D4
POOL_A = (0x2731C, 0x27381)
POOL_B = (0x20600, 0x20654)

MODE_ADDRESS = 0x20000206

LABELS = [
    (0x0A, "Pojemnosc"),
    (0x0B, "Rezystancja"),
    (0x0C, "Napiecie DC"),
    (0x0D, "Napiecie AC"),
    (0x0E, "Ciaglosc"),
    (0x0F, "Czestotliwosc"),
    (0x10, "Prad DC A"),
    (0x11, "Prad DC mA"),
    (0x12, "Temperatura"),
    (0x13, "LIVE"),
    (0x14, "NCV"),
    (0x15, "Prad AC A"),
    (0x16, "Prad AC mA"),
]

# Auto label and the shared fixed-mode label call.  Current modes originally
# draw two JPEG fragments, so their first-fragment calls are replaced by a
# no-op and the common second call draws the complete Polish label once.
DRAW_CALLS = (0xA822, 0xAA34)
SUPPRESS_CALLS = (0xAB06, 0xAB7C)
STOCK_IMAGE_RENDER = 0x678C


def rtype(rd: int, rs1: int, rs2: int, funct3: int = 0,
          funct7: int = 0, opcode: int = 0x33) -> int:
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | \
           (funct3 << 12) | (rd << 7) | opcode


def stype(rs1: int, rs2: int, immediate: int, funct3: int = 2,
          opcode: int = 0x23) -> int:
    value = immediate & 0xFFF
    return ((value >> 5) << 25) | (rs2 << 20) | (rs1 << 15) | \
           (funct3 << 12) | ((value & 0x1F) << 7) | opcode


def encode_jal(pc: int, target: int, rd: int = 1) -> bytes:
    return int(jal(rd, target - pc)).to_bytes(4, "little")


def allocate_strings() -> tuple[dict[int, int], list[tuple[int, bytes]]]:
    pools = [list(POOL_A), list(POOL_B)]
    locations: dict[int, int] = {}
    chunks: list[tuple[int, bytes]] = []
    pool_index = 0
    cursor = pools[0][0]
    for mode, text in LABELS:
        data = text.encode("ascii") + b"\0"
        while cursor + len(data) > pools[pool_index][1]:
            pool_index += 1
            if pool_index >= len(pools):
                raise ValueError("measurement label pools are too small")
            cursor = pools[pool_index][0]
        locations[mode] = cursor
        chunks.append((cursor, data))
        cursor += len(data)
    return locations, chunks


def build_draw_hook() -> bytes:
    table_hi, table_lo = split_address(TABLE)
    pc = DRAW_HOOK
    code = bytearray()

    def emit(word: int) -> None:
        nonlocal pc
        code.extend(int(word).to_bytes(4, "little"))
        pc += 4

    def emit16(data: bytes) -> None:
        nonlocal pc
        if len(data) != 2:
            raise ValueError("compressed instruction must be exactly 2 bytes")
        code.extend(data)
        pc += 2

    emit(itype(0x13, 2, 0, 2, -16))                 # addi sp,sp,-16
    emit(stype(2, 1, 12))                            # sw ra,12(sp)
    emit(lui(REG["t0"], 0x20000))
    emit(itype(0x03, REG["t1"], 4, REG["t0"], MODE_ADDRESS & 0xFFF))
    emit(itype(0x13, REG["t1"], 0, REG["t1"], -0x0A))
    emit(itype(0x13, 7, 3, REG["t1"], len(LABELS))) # sltiu t2,t1,13
    # The mixed 16/32-bit sequence below ends with its epilogue at +88.
    epilogue = DRAW_HOOK + 88
    emit(branch(0, 7, REG["zero"], epilogue - pc))
    emit(lui(REG["t0"], table_hi))
    emit(itype(0x13, REG["t0"], 0, REG["t0"], table_lo))
    emit(itype(0x13, REG["t1"], 1, REG["t1"], 2))  # slli t1,t1,2
    emit(rtype(REG["t0"], REG["t0"], REG["t1"]))
    emit(itype(0x03, 12, 2, REG["t0"], 0))          # lw a2,0(t0)
    emit16(bytes.fromhex("32c4"))                    # c.swsp a2,8(sp)
    emit(jal(1, CLEAR_HOOK - pc))                    # erase previous long label
    emit16(bytes.fromhex("2246"))                    # c.lwsp a2,8(sp)
    emit(itype(0x13, 10, 0, REG["zero"], 104))      # x
    emit(itype(0x13, 11, 0, REG["zero"], 35))       # y
    emit(lui(13, 0x10))                              # yellow RGB565
    emit(itype(0x13, 13, 0, 13, -32))               # 0x0000ffe0
    emit(itype(0x13, 14, 0, 13, 0))
    emit(itype(0x13, 15, 0, REG["zero"], 16))
    emit(itype(0x13, 16, 0, REG["zero"], 1))
    emit(jal(1, ASCII_RENDER - pc))
    emit(itype(0x03, 1, 2, 2, 12))                  # lw ra,12(sp)
    emit(itype(0x13, 2, 0, 2, 16))                  # addi sp,sp,16
    emit(itype(0x67, REG["zero"], 0, 1, 0))         # ret
    return bytes(code)


def build_clear_hook() -> bytes:
    """Clear the complete label band before drawing a shorter next label."""
    data = bytearray()
    data += bytes.fromhex("4111")                    # c.addi sp,-16
    data += bytes.fromhex("06c6")                    # c.swsp ra,12(sp)
    for rd, value in ((10, 80), (11, 25), (12, 240), (13, 58), (14, 0)):
        data += int(itype(0x13, rd, 0, REG["zero"], value)).to_bytes(4, "little")
    call_pc = CLEAR_HOOK + len(data)
    data += int(jal(1, 0x8A02 - call_pc)).to_bytes(4, "little")
    data += bytes.fromhex("b240")                    # c.lwsp ra,12(sp)
    data += bytes.fromhex("4101")                    # c.addi sp,16
    data += bytes.fromhex("8280")                    # c.jr ra
    return bytes(data)


def replace_exact(image: bytearray, address: int, old: bytes, new: bytes) -> None:
    if len(old) != len(new):
        raise ValueError("replacement length mismatch")
    offset = address - LOAD
    if image[offset:offset + len(old)] != old:
        raise SystemExit(f"Unexpected bytes at 0x{address:08X}; refusing to patch")
    image[offset:offset + len(new)] = new


def require_zero(image: bytearray, start: int, end: int, name: str) -> None:
    if any(image[start - LOAD:end - LOAD]):
        raise SystemExit(f"{name} at 0x{start:X}..0x{end:X} is not empty")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    source = args.source.read_bytes()
    image = bytearray(source)
    hook = build_draw_hook()
    clear_hook = build_clear_hook()
    if DRAW_HOOK + len(hook) > DRAW_HOOK_LIMIT:
        raise SystemExit("measurement draw hook does not fit")
    require_zero(image, DRAW_HOOK, DRAW_HOOK_LIMIT, "draw hook cave")
    require_zero(image, NOOP_HOOK, POOL_B[1], "secondary cave")
    require_zero(image, TABLE, TABLE + len(LABELS) * 4, "label table cave")
    require_zero(image, POOL_A[0], POOL_A[1], "primary string cave")

    locations, string_chunks = allocate_strings()
    table = b"".join(struct.pack("<I", locations[mode]) for mode, _ in LABELS)
    image[DRAW_HOOK - LOAD:DRAW_HOOK - LOAD + len(hook)] = hook
    image[NOOP_HOOK - LOAD:NOOP_HOOK - LOAD + 4] = int(
        itype(0x67, REG["zero"], 0, 1, 0)
    ).to_bytes(4, "little")
    if CLEAR_HOOK + len(clear_hook) > POOL_B[1]:
        raise SystemExit("label clear hook does not fit")
    image[CLEAR_HOOK - LOAD:CLEAR_HOOK - LOAD + len(clear_hook)] = clear_hook
    image[TABLE - LOAD:TABLE - LOAD + len(table)] = table
    for address, data in string_chunks:
        image[address - LOAD:address - LOAD + len(data)] = data

    for address in DRAW_CALLS:
        replace_exact(image, address,
                      encode_jal(address, STOCK_IMAGE_RENDER),
                      encode_jal(address, DRAW_HOOK))
    for address in SUPPRESS_CALLS:
        replace_exact(image, address,
                      encode_jal(address, STOCK_IMAGE_RENDER),
                      encode_jal(address, NOOP_HOOK))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    report = {
        "definition": "Polish regular-view measurement names instead of mode symbols",
        "source": str(args.source),
        "output": str(args.output),
        "size": len(image),
        "source_sha256": hashlib.sha256(source).hexdigest().upper(),
        "output_sha256": hashlib.sha256(image).hexdigest().upper(),
        "labels": [{"mode": hex(mode), "text": text,
                    "address": hex(locations[mode])} for mode, text in LABELS],
        "draw_hook": hex(DRAW_HOOK),
        "clear_hook": hex(CLEAR_HOOK),
        "draw_call_sites": [hex(x) for x in DRAW_CALLS],
        "suppressed_fragment_calls": [hex(x) for x in SUPPRESS_CALLS],
        "polish_characters": "ASCII fallback; no diacritics in this version",
    }
    manifest = args.manifest or args.output.with_suffix(".json")
    manifest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

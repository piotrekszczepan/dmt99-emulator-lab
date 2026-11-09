#!/usr/bin/env python3
"""Render the Polish Theme 2 menu without modifying the external W25Q64.

The stock Theme 2 menu uses German JPEG labels because Polish reuses language
slot 2 (the original German resource directory).  This patch redirects only
the Theme 2 menu JPEG call sites.  For Polish + Theme 2 it draws compact ASCII
labels with the firmware's own rectangle/text primitives.  Theme 1, English,
measurements, calibration and the W25Q64 remain untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from patch_dmt99_embedded_polish import (
    ASCII_RENDER,
    LOAD,
    REG,
    branch as encode_branch,
    itype,
    jal,
    lui,
    pack,
    split_address,
)


IMAGE_RENDER = 0x678C
FILL_RECT = 0x8A02
HOOK = 0x27400
LANGUAGE_WRAPPER = 0x275D0
TABLE = 0x27700
OPS = 0x27A00
STRINGS = 0x28600
CODE_LIMIT = 0x30000

CALL_SITES = (
    0x15C5C, 0x15C82,
    0x16ACC, 0x16AF0, 0x16B3E, 0x16B66, 0x16B8E,
    0x16F5E, 0x16F84, 0x16FBC, 0x16FE4, 0x1700C,
    0x172AC, 0x172D2, 0x1730C, 0x1739C,
    0x1794C, 0x17972, 0x17A26, 0x17A86, 0x17AAC,
)
LANGUAGE_REDRAW_CALL = 0x15D14
LANGUAGE_WRAPPER_CALL_BASE = LANGUAGE_WRAPPER + 64
LANGUAGE_WRAPPER_CALL_SELECTED = LANGUAGE_WRAPPER + 84

BLACK = 0x0000
GRAY = 0x39E7
WHITE = 0xFFFF
YELLOW = 0xFFE0


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
    return struct.pack("<I", jal(rd, target - pc))


class Assembler:
    def __init__(self, origin: int):
        self.origin = origin
        self.words: list[int] = []
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str, tuple]] = []

    @property
    def pc(self) -> int:
        return self.origin + len(self.words) * 4

    def emit(self, word: int) -> None:
        self.words.append(word)

    def label(self, name: str) -> None:
        self.labels[name] = self.pc

    def b(self, funct3: int, rs1: int, rs2: int, label: str) -> None:
        self.fixups.append((len(self.words), "b", (funct3, rs1, rs2, label)))
        self.emit(0)

    def j(self, label: str) -> None:
        self.fixups.append((len(self.words), "j", (label,)))
        self.emit(0)

    def call(self, target: int) -> None:
        self.emit(jal(1, target - self.pc))

    def la(self, rd: int, address: int) -> None:
        hi, lo = split_address(address)
        self.emit(lui(rd, hi))
        self.emit(itype(0x13, rd, 0, rd, lo))

    def build(self) -> bytes:
        for index, kind, args in self.fixups:
            pc = self.origin + index * 4
            if kind == "b":
                funct3, rs1, rs2, label = args
                self.words[index] = encode_branch(
                    funct3, rs1, rs2, self.labels[label] - pc
                )
            else:
                (label,) = args
                self.words[index] = jal(REG["zero"], self.labels[label] - pc)
        return pack(self.words)


def build_hook() -> bytes:
    a = Assembler(HOOK)

    # Preserve the caller and the original renderer arguments.
    a.emit(itype(0x13, 2, 0, 2, -32))
    for reg, offset in ((1, 28), (8, 24), (9, 20), (18, 16),
                        (19, 12), (20, 8), (21, 4), (22, 0)):
        a.emit(stype(2, reg, offset))
    a.emit(itype(0x13, 8, 0, 10, 0))   # s0 = path
    a.emit(itype(0x13, 9, 0, 11, 0))   # s1 = x
    a.emit(itype(0x13, 18, 0, 12, 0))  # s2 = y
    a.emit(itype(0x13, 22, 0, 1, 0))   # s6 = original ra

    # The settings screen previews a language/theme before committing it to
    # 0x2000003e.  Therefore the stored indices are stale exactly while the
    # user highlights Theme 2 or changes English -> Polski.  Detect the real
    # Polish resource path (menu/german/) at these Theme-2-only call sites.
    # This covers the live Theme-2 preview before its stored layout bit changes.
    for offset, character in ((5, "g"), (6, "e"), (7, "r")):
        a.emit(itype(0x03, REG["t0"], 4, 8, offset))
        a.emit(itype(0x13, REG["t1"], 0, REG["zero"], ord(character)))
        a.b(1, REG["t0"], REG["t1"], "stored_check")
    a.j("lookup_start")

    # A confirmed Theme 2 and the About body use paths that are not always
    # distinguishable at the call boundary.  Accept the stored Polish+Theme2
    # state as well.  English still falls through unchanged.
    a.label("stored_check")
    a.emit(lui(REG["t0"], 0x20000))
    a.emit(itype(0x03, 20, 5, REG["t0"], 0x3E))
    a.emit(itype(0x13, REG["t0"], 7, 20, 7))
    a.emit(itype(0x13, REG["t1"], 0, REG["zero"], 2))
    a.b(1, REG["t0"], REG["t1"], "fallback")
    a.emit(itype(0x13, REG["t0"], 5, 20, 10))
    a.emit(itype(0x13, REG["t0"], 7, REG["t0"], 3))
    a.emit(itype(0x13, REG["t1"], 0, REG["zero"], 1))
    a.b(1, REG["t0"], REG["t1"], "fallback")
    a.j("lookup_start")

    a.label("lookup_start")
    a.la(19, TABLE)
    a.label("lookup")
    a.emit(itype(0x03, REG["t0"], 2, 19, 0))
    a.b(0, REG["t0"], REG["zero"], "fallback")
    a.b(1, REG["t0"], 22, "next")
    a.emit(itype(0x03, REG["t0"], 5, 19, 4))
    a.b(1, REG["t0"], 9, "next")
    a.emit(itype(0x03, REG["t0"], 5, 19, 6))
    a.b(1, REG["t0"], 18, "next")
    a.emit(itype(0x03, 21, 2, 19, 12))  # s5 = default ops
    a.emit(itype(0x03, REG["t0"], 4, 19, 8))
    a.b(0, REG["t0"], REG["zero"], "ops")
    a.emit(itype(0x13, REG["t1"], 0, REG["zero"], 1))
    a.b(1, REG["t0"], REG["t1"], "path_selector")
    a.emit(itype(0x03, REG["t1"], 4, 19, 9))
    a.emit(itype(0x13, 7, 5, 20, 8))
    a.emit(itype(0x13, 7, 7, 7, 3))
    a.b(1, REG["t1"], 7, "ops")
    a.emit(itype(0x03, 21, 2, 19, 16))
    a.j("ops")

    a.label("path_selector")
    a.emit(itype(0x13, REG["t1"], 0, REG["zero"], 2))
    a.b(1, REG["t0"], REG["t1"], "ops")
    a.emit(itype(0x03, REG["t1"], 4, 19, 9))
    a.emit(rtype(REG["t1"], 8, REG["t1"]))
    a.emit(itype(0x03, REG["t1"], 4, REG["t1"], 0))
    a.emit(itype(0x03, 7, 4, 19, 10))
    a.b(1, REG["t1"], 7, "ops")
    a.emit(itype(0x03, 21, 2, 19, 16))
    a.j("ops")

    a.label("next")
    a.emit(itype(0x13, 19, 0, 19, 20))
    a.j("lookup")

    a.label("ops")
    a.emit(itype(0x03, REG["t0"], 4, 21, 0))
    a.b(0, REG["t0"], REG["zero"], "done")
    a.emit(itype(0x13, REG["t1"], 0, REG["zero"], 1))
    a.b(0, REG["t0"], REG["t1"], "fill")

    # Text record: x,y,color,font,string pointer.
    a.emit(itype(0x03, 10, 5, 21, 2))
    a.emit(itype(0x03, 11, 5, 21, 4))
    a.emit(itype(0x03, 13, 5, 21, 6))
    a.emit(itype(0x13, 14, 0, 13, 0))
    a.emit(itype(0x03, 15, 5, 21, 10))
    a.emit(itype(0x03, 12, 2, 21, 12))
    a.emit(itype(0x13, 16, 0, REG["zero"], 1))
    a.call(ASCII_RENDER)
    a.emit(itype(0x13, 21, 0, 21, 16))
    a.j("ops")

    # Fill record: x1,y1,x2,y2,color.
    a.label("fill")
    a.emit(itype(0x03, 10, 5, 21, 2))
    a.emit(itype(0x03, 11, 5, 21, 4))
    a.emit(itype(0x03, 12, 5, 21, 6))
    a.emit(itype(0x03, 13, 5, 21, 8))
    a.emit(itype(0x03, 14, 5, 21, 10))
    a.call(FILL_RECT)
    a.emit(itype(0x13, 21, 0, 21, 16))
    a.j("ops")

    a.label("fallback")
    a.emit(itype(0x13, 10, 0, 8, 0))
    a.emit(itype(0x13, 11, 0, 9, 0))
    a.emit(itype(0x13, 12, 0, 18, 0))
    a.call(IMAGE_RENDER)
    a.j("epilogue")

    a.label("done")
    a.emit(itype(0x13, 10, 0, REG["zero"], 0))
    a.label("epilogue")
    for reg, offset in ((22, 0), (21, 4), (20, 8), (19, 12),
                        (18, 16), (9, 20), (8, 24), (1, 28)):
        a.emit(itype(0x03, reg, 2, 2, offset))
    a.emit(itype(0x13, 2, 0, 2, 32))
    a.emit(itype(0x67, REG["zero"], 0, 1, 0))
    return a.build()


def build_language_wrapper(base_path: int, selected_path: int) -> bytes:
    """Finish the stock repaint, then replace its Theme-2 left menu in Polish."""
    a = Assembler(LANGUAGE_WRAPPER)
    a.emit(itype(0x13, 2, 0, 2, -16))
    a.emit(stype(2, 1, 12))
    a.call(0x153D0)

    a.emit(lui(REG["t0"], 0x20000))
    a.emit(itype(0x03, 7, 5, REG["t0"], 0x3E))
    a.emit(itype(0x13, REG["t0"], 7, 7, 7))
    a.emit(itype(0x13, REG["t1"], 0, REG["zero"], 2))
    a.b(1, REG["t0"], REG["t1"], "done")
    a.emit(itype(0x13, REG["t0"], 5, 7, 10))
    a.emit(itype(0x13, REG["t0"], 7, REG["t0"], 3))
    a.emit(itype(0x13, REG["t1"], 0, REG["zero"], 1))
    a.b(1, REG["t0"], REG["t1"], "done")

    a.la(10, base_path)
    a.emit(itype(0x13, 11, 0, REG["zero"], 0))
    a.emit(itype(0x13, 12, 0, REG["zero"], 0))
    if a.pc != LANGUAGE_WRAPPER_CALL_BASE:
        raise ValueError("unexpected base redraw call address")
    a.call(HOOK)

    a.la(10, selected_path)
    a.emit(itype(0x13, 11, 0, REG["zero"], 0))
    a.emit(itype(0x13, 12, 0, REG["zero"], 120))
    if a.pc != LANGUAGE_WRAPPER_CALL_SELECTED:
        raise ValueError("unexpected selected-row redraw call address")
    a.call(HOOK)

    a.label("done")
    a.emit(itype(0x03, 1, 2, 2, 12))
    a.emit(itype(0x13, 2, 0, 2, 16))
    a.emit(itype(0x67, REG["zero"], 0, 1, 0))
    return a.build()


class Assets:
    def __init__(self):
        self.strings = bytearray()
        self.string_addresses: dict[str, int] = {}
        self.ops = bytearray()
        self.op_addresses: dict[str, int] = {}

    def string(self, text: str) -> int:
        if text not in self.string_addresses:
            address = STRINGS + len(self.strings)
            self.string_addresses[text] = address
            self.strings += text.encode("ascii") + b"\0"
        return self.string_addresses[text]

    @staticmethod
    def fill(x1: int, y1: int, x2: int, y2: int, color: int) -> tuple:
        return (1, x1, y1, x2, y2, color, None)

    @staticmethod
    def text(x: int, y: int, color: int, value: str) -> tuple:
        return (2, x, y, color, 0, 16, value)

    def add_ops(self, name: str, records: list[tuple]) -> int:
        address = OPS + len(self.ops)
        self.op_addresses[name] = address
        for kind, x, y, u, v, w, value in records:
            pointer = 0 if value is None else self.string(value)
            self.ops += struct.pack("<BBHHHHHI", kind, 0, x, y, u, v, w, pointer)
        self.ops += b"\0" * 16
        return address


def build_assets() -> tuple[Assets, bytes]:
    a = Assets()
    f, t = a.fill, a.text

    base = [f(0, 0, 130, 239, BLACK)]
    base += [f(0, y, 130, y, GRAY) for y in (39, 79, 119, 159, 199)]
    base += [
        t(21, 12, WHITE, "Wybor trybu"),
        t(22, 43, WHITE, "Ustawienia"), t(42, 59, WHITE, "progow"),
        t(33, 92, WHITE, "Historia"),
        t(22, 123, WHITE, "Ustawienia"), t(34, 139, WHITE, "systemu"),
        t(43, 172, WHITE, "Reset"), t(25, 212, WHITE, "O mierniku"),
    ]
    a.add_ops("base", base)

    # The stock system/about right panel clears the upper strip after the
    # left menu base has been rendered.  Move only the first label lower on
    # those two pages so it remains visible; drawing it again later changes
    # the display window used by the stock right-panel text renderer.
    base_low_top = [f(0, 0, 130, 239, BLACK)]
    base_low_top += [f(0, y, 130, y, GRAY) for y in (39, 79, 119, 159, 199)]
    base_low_top += [
        t(21, 23, WHITE, "Wybor trybu"),
        t(22, 43, WHITE, "Ustawienia"), t(42, 59, WHITE, "progow"),
        t(33, 92, WHITE, "Historia"),
        t(22, 123, WHITE, "Ustawienia"), t(34, 139, WHITE, "systemu"),
        t(43, 172, WHITE, "Reset"), t(25, 212, WHITE, "O mierniku"),
    ]
    a.add_ops("base_low_top", base_low_top)

    rows = {
        "row0": (0, 39, [(21, 12, "Wybor trybu")]),
        "row1": (40, 79, [(22, 43, "Ustawienia"), (42, 59, "progow")]),
        "row2": (80, 119, [(33, 92, "Historia")]),
        "row3": (120, 159, [(22, 123, "Ustawienia"), (34, 139, "systemu")]),
        "row4": (160, 199, [(43, 172, "Reset")]),
        "row5": (200, 239, [(25, 212, "O mierniku")]),
    }
    for name, (y1, y2, labels) in rows.items():
        records = [f(0, y1, 130, y2, YELLOW)]
        records += [t(x, y, BLACK, value) for x, y, value in labels]
        a.add_ops(name, records)

    for index, (name, y, label) in enumerate((
        ("view1", 53, "Pomiar"),
        ("view2", 103, "Rejestracja"),
        ("view3", 153, "Monitor"),
    ), 1):
        a.add_ops(name + "_off", [
            f(157, y, 293, y + 33, BLACK),
            f(157, y + 8, 174, y + 25, WHITE),
            f(159, y + 10, 172, y + 23, BLACK),
            t(184, y + 8, WHITE, label),
        ])
        a.add_ops(name + "_on", [
            f(157, y, 293, y + 33, BLACK),
            f(157, y + 8, 174, y + 25, YELLOW),
            t(184, y + 8, YELLOW, label),
        ])

    a.add_ops("voltage", [f(136, 7, 306, 26, BLACK), t(136, 9, WHITE, "Napiecie:")])
    a.add_ops("current", [f(136, 84, 306, 103, BLACK), t(136, 86, WHITE, "Prad:")])
    a.add_ops("temperature", [f(136, 162, 306, 181, BLACK), t(136, 164, WHITE, "Temperatura:")])
    a.add_ops("history_header", [
        f(131, 15, 319, 34, BLACK),
        t(150, 17, YELLOW, "Tryb"), t(235, 17, YELLOW, "Pomiar"),
    ])

    a.add_ops("about_panel", [
        f(131, 0, 319, 239, BLACK),
        t(158, 24, YELLOW, "FNIRSI DMT-99"),
        t(151, 62, WHITE, "Miernik cyfrowy"),
        t(151, 96, WHITE, "Firmware V2.4 PL"),
        t(151, 130, WHITE, "Motyw 2: polski"),
    ])

    a.add_ops("reset_dialog", [
        f(131, 0, 319, 239, BLACK),
        f(141, 10, 309, 40, YELLOW), t(201, 17, BLACK, "UWAGA"),
        t(145, 58, YELLOW, "Przywrocic"),
        t(145, 76, YELLOW, "wszystkie ustawienia?"),
        f(143, 147, 308, 177, GRAY), t(195, 154, WHITE, "Resetuj"),
        f(143, 188, 308, 218, GRAY), t(199, 195, WHITE, "Powrot"),
    ])
    a.add_ops("reset_button", [
        f(143, 147, 308, 177, YELLOW), t(195, 154, BLACK, "Resetuj"),
        f(143, 188, 308, 218, GRAY), t(199, 195, WHITE, "Powrot"),
    ])
    a.add_ops("return_button", [
        f(143, 147, 308, 177, GRAY), t(195, 154, WHITE, "Resetuj"),
        f(143, 188, 308, 218, YELLOW), t(199, 195, BLACK, "Powrot"),
    ])

    rows_data = []

    def row(site: int, x: int, y: int, ops0: str,
            selector: int = 0, value: int = 0, match: int = 0,
            ops1: str | None = None) -> None:
        rows_data.append(struct.pack(
            "<IHHBBBBII", site + 4, x, y, selector, value, match, 0,
            a.op_addresses[ops0],
            a.op_addresses[ops1] if ops1 else 0,
        ))

    for site in (0x16ACC, 0x16F5E, 0x172AC, 0x1794C, 0x17A86):
        row(site, 0, 0, "base")
    row(0x15C5C, 0, 0, "base")
    row(0x15C82, 0, 120, "row3")
    row(LANGUAGE_WRAPPER_CALL_BASE, 0, 0, "base")
    row(LANGUAGE_WRAPPER_CALL_SELECTED, 0, 120, "row3")
    for site in (0x1739C,):
        row(site, 0, 0, "base_low_top")
    row(0x16AF0, 0, 0, "row0")
    row(0x16F84, 0, 40, "row1")
    row(0x172D2, 0, 80, "row2")
    row(0x16B8E, 0, 120, "row3")
    row(0x17972, 0, 160, "row4")
    row(0x17AAC, 0, 200, "row5")
    row(0x16B3E, 157, 53, "view1_off", 1, 1, 0, "view1_on")
    row(0x16B66, 157, 103, "view2_off", 1, 2, 0, "view2_on")
    row(0x16B8E, 157, 153, "view3_off", 1, 3, 0, "view3_on")
    row(0x16FBC, 136, 7, "voltage")
    row(0x16FE4, 136, 84, "current")
    row(0x1700C, 136, 162, "temperature")
    row(0x1730C, 131, 15, "history_header")
    row(0x17A26, 131, 50, "about_panel")
    row(0x16B8E, 131, 0, "reset_dialog")
    row(0x16B8E, 143, 147, "reset_button", 2, 21, ord("2"), "return_button")
    rows_data.append(b"\0" * 20)
    a.string("menu/german/mode_set.jpg")
    a.string("menu/german/install.jpg")
    return a, b"".join(rows_data)


def write_at(image: bytearray, address: int, data: bytes) -> None:
    offset = address - LOAD
    end = offset + len(data)
    if end > len(image):
        image.extend(b"\0" * (end - len(image)))
    image[offset:end] = data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    source = args.source.read_bytes()
    image = bytearray(source)
    source_end = LOAD + len(source)
    if source_end > HOOK:
        raise SystemExit(f"source ends at 0x{source_end:X}, overlaps Theme 2 hook")

    assets, table = build_assets()
    hook = build_hook()
    if HOOK + len(hook) > LANGUAGE_WRAPPER:
        raise SystemExit("Theme 2 hook does not fit before language wrapper")
    language_wrapper = build_language_wrapper(
        assets.string_addresses["menu/german/mode_set.jpg"],
        assets.string_addresses["menu/german/install.jpg"],
    )
    if LANGUAGE_WRAPPER + len(language_wrapper) > TABLE:
        raise SystemExit("language wrapper does not fit before its table")
    if TABLE + len(table) > OPS:
        raise SystemExit("Theme 2 call table does not fit")
    if OPS + len(assets.ops) > STRINGS:
        raise SystemExit("Theme 2 drawing operations do not fit")
    if STRINGS + len(assets.strings) > CODE_LIMIT:
        raise SystemExit("Theme 2 strings exceed the verified application limit")

    stock_call_mismatches = []
    for site in CALL_SITES:
        offset = site - LOAD
        expected = encode_jal(site, IMAGE_RENDER)
        if image[offset:offset + 4] != expected:
            stock_call_mismatches.append(hex(site))
        else:
            image[offset:offset + 4] = encode_jal(site, HOOK)
    if stock_call_mismatches:
        raise SystemExit(
            "unexpected Theme 2 image calls at " + ", ".join(stock_call_mismatches)
        )

    language_offset = LANGUAGE_REDRAW_CALL - LOAD
    language_expected = encode_jal(LANGUAGE_REDRAW_CALL, 0x153D0)
    if image[language_offset:language_offset + 4] != language_expected:
        raise SystemExit("unexpected post-language repaint call")
    image[language_offset:language_offset + 4] = encode_jal(
        LANGUAGE_REDRAW_CALL, LANGUAGE_WRAPPER
    )

    write_at(image, HOOK, hook)
    write_at(image, LANGUAGE_WRAPPER, language_wrapper)
    write_at(image, TABLE, table)
    write_at(image, OPS, assets.ops)
    write_at(image, STRINGS, assets.strings)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    report = {
        "definition": "Polish Theme 2 menu rendered from firmware; no W25Q64 writes",
        "source": str(args.source),
        "output": str(args.output),
        "source_size": len(source),
        "output_size": len(image),
        "source_sha256": hashlib.sha256(source).hexdigest().upper(),
        "output_sha256": hashlib.sha256(image).hexdigest().upper(),
        "hook": hex(HOOK),
        "language_wrapper": hex(LANGUAGE_WRAPPER),
        "table": hex(TABLE),
        "operations": hex(OPS),
        "strings": hex(STRINGS),
        "patched_call_sites": [hex(x) for x in CALL_SITES],
        "patched_post_language_repaint_call": hex(LANGUAGE_REDRAW_CALL),
        "active_when": {
            "theme2_resource_prefix": "menu/german/",
            "stored_state": {"language_index": 2, "layout_index": 1},
            "preview_safe_before_settings_commit": True,
            "english_to_polish_redraw": True,
        },
        "w25q64_modified": False,
        "measurement_rendering_modified": False,
        "theme1_modified": False,
        "english_modified": False,
    }
    manifest = args.manifest or args.output.with_suffix(".json")
    manifest.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

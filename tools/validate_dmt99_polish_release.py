#!/usr/bin/env python3
"""End-to-end emulator validation for the Polish-only DMT-99 V2.4 image.

This checks the real RV32 firmware in Unicorn with the stock W25Q64 dump.  It
does not claim analogue accuracy, electrical safety or physical-device proof.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
RESEARCH = Path(os.environ.get("DMT99_RESEARCH_DIR", ROOT / "vendor" / "dmt99-research"))
PACKAGE = Path(os.environ.get("DMT99_IMAGES_DIR", ROOT / "images"))
sys.path[:0] = [str(RESEARCH / ".deps"), str(RESEARCH / "tools")]

from fw_emulator import Ch32Emulator
from test_firmware_emulation import ack_packet, battery_raw, reading_packet, settings_image


FIRMWARE = PACKAGE / "DMT-99_V2.4_PL_ONLY_LABELS.BIN"
BASELINE = PACKAGE / "DMT-99_V2.4_20240306_PL_ONLY_LOCKED.BIN"
STOCK_FLASH = RESEARCH / "flashdump" / "dmt99_flash_1.bin"
PINS = {1: "PC10", 2: "PC11", 3: "PC9", 4: "PC12", 5: "PC8", 6: "PC8"}
LABEL_BOX = (80, 25, 241, 59)

MODES = [
    (0x0A, "Pojemnosc", 16),
    (0x0B, "Rezystancja", 13),
    (0x0C, "Napiecie DC", 6),
    (0x0D, "Napiecie AC", 6),
    (0x0E, "Ciaglosc", 11),
    (0x0F, "Czestotliwosc", 18),
    (0x10, "Prad DC A", 10),
    (0x11, "Prad DC mA", 9),
    (0x12, "Temperatura", 21),
    (0x15, "Prad AC A", 10),
    (0x16, "Prad AC mA", 9),
]


def make(firmware: Path = FIRMWARE, layout: int = 1, language: int = 1) -> Ch32Emulator:
    emu = Ch32Emulator(
        original=True,
        bin_path=firmware,
        flash_dump=STOCK_FLASH,
        settings=settings_image(view=1, layout=layout, english=language),
        battery_raw=battery_raw(87),
    )
    emu.run(seconds=4)
    return emu


def press(emu: Ch32Emulator, key: int) -> None:
    emu.press(PINS[key], hold=0.8 if key == 6 else 0.12)
    emu.run(seconds=1.25)


def state(emu: Ch32Emulator) -> dict:
    word = int.from_bytes(emu.uc.mem_read(0x2000003E, 2), "little")
    prefix = bytes(emu.uc.mem_read(0x20000298, 48)).split(b"\0")[0].decode("ascii")
    return {
        "fault": emu.fault,
        "halted": emu.halted,
        "main_loop_entered": emu.loop_entered,
        "stored_language": word & 7,
        "stored_layout": (word >> 10) & 3,
        "resource_prefix": prefix,
        "framebuffer_sha256": emu.panel.checksum(),
        "w25q_erases": len(emu.nor.erases),
        "w25q_programs": len(emu.nor.programs),
    }


def open_system(emu: Ch32Emulator) -> None:
    for key in (6, 1, 1, 1, 3):
        press(emu, key)


def label_metrics(emu: Ch32Emulator) -> dict:
    crop = emu.panel.image().crop(LABEL_BOX)
    yellow = sum(1 for red, green, blue in crop.getdata()
                 if red >= 160 and green >= 130 and blue <= 120)
    return {
        "crop_sha256": hashlib.sha256(crop.tobytes()).hexdigest(),
        "yellow_pixels": yellow,
    }


def set_mode(emu: Ch32Emulator, mode: int, unit: int) -> None:
    emu.frame(ack_packet(mode))
    emu.run(seconds=0.8)
    emu.frame(reading_packet("12.34", unit))
    emu.run(seconds=1.5)


def validate_labels() -> tuple[list[dict], bool]:
    gallery: list[tuple[str, Image.Image]] = []
    results: list[dict] = []
    sequential = make(layout=0, language=2)

    for mode, label, unit in MODES:
        fresh = make(layout=0, language=2)
        set_mode(fresh, mode, unit)
        fresh_metrics = label_metrics(fresh)

        set_mode(sequential, mode, unit)
        sequential_metrics = label_metrics(sequential)
        image = sequential.panel.image()
        image.save(PACKAGE / f"emulacja-etykieta-{mode:02x}.png")
        gallery.append((label, image))

        clean_transition = fresh_metrics["crop_sha256"] == sequential_metrics["crop_sha256"]
        visible = sequential_metrics["yellow_pixels"] >= 20
        results.append({
            "mode": f"0x{mode:02X}",
            "label": label,
            "visible_yellow_text": visible,
            "clean_transition_equals_fresh_render": clean_transition,
            "fresh": fresh_metrics,
            "sequential": sequential_metrics,
            "healthy": fresh.fault is None and sequential.fault is None
                       and not fresh.halted and not sequential.halted,
        })

    sheet = Image.new("RGB", (640, 3 * 280), "#20252b")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(gallery):
        col, row = index % 2, index // 2
        x, y = col * 320, row * 140
        thumb = image.resize((320, 240)).crop((0, 0, 320, 125))
        sheet.paste(thumb, (x, y + 15))
        draw.text((x + 6, y + 1), label, fill="white")
    sheet.save(PACKAGE / "emulacja-polskie-nazwy-pomiarow.png")

    passed = all(item["visible_yellow_text"]
                 and item["clean_transition_equals_fresh_render"]
                 and item["healthy"] for item in results)
    return results, passed


def main() -> None:
    boot = make()
    baseline = make(BASELINE)
    boot_state = state(boot)
    baseline_state = state(baseline)
    boot.panel.save(PACKAGE / "emulacja-final-start.png")

    language = make(layout=0, language=2)
    open_system(language)
    for key in (1, 1, 1, 5):
        press(language, key)
    language_state = state(language)

    theme = make(layout=0, language=2)
    open_system(theme)
    for key in (1, 5):
        press(theme, key)
    theme_state = state(theme)

    label_results, labels_pass = validate_labels()
    healthy = all(s["fault"] is None and not s["halted"] and s["main_loop_entered"]
                  for s in (boot_state, language_state, theme_state))
    polish_locked = all(s["stored_language"] == 2
                        for s in (boot_state, language_state, theme_state))
    theme_locked = all(s["stored_layout"] == 0
                       for s in (boot_state, language_state, theme_state))
    no_extra_w25q_writes = (
        boot_state["w25q_erases"] == baseline_state["w25q_erases"]
        and boot_state["w25q_programs"] == baseline_state["w25q_programs"]
    )
    passed = healthy and polish_locked and theme_locked and no_extra_w25q_writes and labels_pass
    report = {
        "definition": "DMT-99 V2.4 Polish-only release with ASCII measurement names",
        "pass": passed,
        "scope": "RV32 firmware emulator plus stock W25Q64 model; not physical analogue validation",
        "firmware": str(FIRMWARE),
        "firmware_size": FIRMWARE.stat().st_size,
        "firmware_sha256": hashlib.sha256(FIRMWARE.read_bytes()).hexdigest().upper(),
        "healthy": healthy,
        "language_locked_to_polish_index_2": polish_locked,
        "theme_locked_to_theme1_layout_0": theme_locked,
        "no_patch_specific_extra_w25q64_writes": no_extra_w25q_writes,
        "boot_from_english_theme2": boot_state,
        "baseline_boot": baseline_state,
        "after_attempted_english_selection": language_state,
        "after_attempted_theme2_selection": theme_state,
        "measurement_labels_pass": labels_pass,
        "measurement_labels": label_results,
        "polish_characters": "ASCII fallback without diacritics",
    }
    (PACKAGE / "POLISH_RELEASE_VALIDATION.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()

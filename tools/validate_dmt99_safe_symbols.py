#!/usr/bin/env python3
"""Validate the rollback-safe DMT-99 image with stock measurement symbols."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RESEARCH = Path(os.environ.get("DMT99_RESEARCH_DIR", ROOT / "vendor" / "dmt99-research"))
PACKAGE = Path(os.environ.get("DMT99_IMAGES_DIR", ROOT / "images"))
sys.path[:0] = [str(RESEARCH / ".deps"), str(RESEARCH / "tools")]

from fw_emulator import Ch32Emulator
from test_firmware_emulation import ack_packet, battery_raw, reading_packet, settings_image


FIRMWARE = PACKAGE / "DMT-99_V2.4_PL_EN_SYMBOLS_THEME1.BIN"
BASELINE = PACKAGE / "DMT-99_V2.4_PL_EN_SYMBOLS_THEME1_V2.BIN"
STOCK_FLASH = RESEARCH / "flashdump" / "dmt99_flash_1.bin"
LOAD = 0x6400
PINS = {1: "PC10", 2: "PC11", 3: "PC9", 4: "PC12", 5: "PC8", 6: "PC8"}


def make(firmware: Path = FIRMWARE, *, language: int | None = 2,
         layout: int = 0) -> Ch32Emulator:
    fixture = None if language is None else settings_image(view=1, layout=layout, english=language)
    emu = Ch32Emulator(original=True, bin_path=firmware, flash_dump=STOCK_FLASH,
                       settings=fixture, battery_raw=battery_raw(87))
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


def measurement_region_sha256(emu: Ch32Emulator) -> str:
    """Hash the measurement UI while excluding the time-varying battery bar."""
    image = emu.panel.image().crop((0, 20, 320, 240))
    return hashlib.sha256(image.tobytes()).hexdigest()


def open_system(emu: Ch32Emulator) -> None:
    for key in (6, 1, 1, 1, 3):
        press(emu, key)


def open_thresholds(emu: Ch32Emulator) -> None:
    for key in (6, 1, 3):
        press(emu, key)


def open_history(emu: Ch32Emulator) -> None:
    for key in (6, 1, 1, 3):
        press(emu, key)


def binary_diff_ranges() -> list[dict]:
    base, candidate = BASELINE.read_bytes(), FIRMWARE.read_bytes()
    changed = [index for index, pair in enumerate(zip(base, candidate)) if pair[0] != pair[1]]
    ranges: list[dict] = []
    if not changed:
        return ranges
    start = previous = changed[0]
    for index in changed[1:]:
        if index != previous + 1:
            ranges.append({"start": hex(LOAD + start), "end": hex(LOAD + previous + 1)})
            start = index
        previous = index
    ranges.append({"start": hex(LOAD + start), "end": hex(LOAD + previous + 1)})
    return ranges


def binary_changes_confined() -> bool:
    base, candidate = BASELINE.read_bytes(), FIRMWARE.read_bytes()
    allowed = (
        range(0x14D2E - LOAD, 0x14D32 - LOAD),
        range(0x1EC64 - LOAD, 0x1EC8C - LOAD),
        range(0x205FC - LOAD, 0x20654 - LOAD),
        range(0x27336 - LOAD, 0x27381 - LOAD),
    )
    return all(any(index in region for region in allowed)
               for index, pair in enumerate(zip(base, candidate)) if pair[0] != pair[1])


def main() -> None:
    default = make(language=None)
    default_state = state(default)
    default.panel.save(PACKAGE / "emulacja-bezpieczna-symbole-start.png")

    english = make(language=2)
    open_system(english)
    for key in (1, 1, 1, 5):
        press(english, key)
    english_state = state(english)
    english.panel.save(PACKAGE / "emulacja-bezpieczna-english.png")

    theme = make(language=2)
    open_system(theme)
    for key in (1, 5):
        press(theme, key)
    theme_state = state(theme)

    thresholds = make(language=2)
    open_thresholds(thresholds)
    thresholds_state = state(thresholds)
    thresholds.panel.save(PACKAGE / "emulacja-v3-progi.png")

    history = make(language=2)
    open_history(history)
    history_state = state(history)
    history.panel.save(PACKAGE / "emulacja-v3-historia.png")

    polish_charging_baseline = make(BASELINE, language=2)
    polish_charging_baseline.charging = True
    polish_charging_baseline.run(seconds=2.5)

    polish_charging = make(language=2)
    polish_charging.charging = True
    polish_charging.run(seconds=2.5)
    polish_charging_state = state(polish_charging)
    polish_charging.panel.save(PACKAGE / "emulacja-v3-ladowanie-pl.png")

    english_charging_baseline = make(BASELINE, language=1)
    english_charging_baseline.charging = True
    english_charging_baseline.run(seconds=2.5)

    english_charging = make(language=1)
    english_charging.charging = True
    english_charging.run(seconds=2.5)
    english_charging_state = state(english_charging)
    english_charging.panel.save(PACKAGE / "emulacja-v3-ladowanie-en.png")

    baseline = make(BASELINE, language=2)
    candidate = make(language=2)
    symbol_checks = []
    for mode, unit, name in ((0x0C, 6, "voltage_dc"),
                             (0x0F, 18, "frequency"),
                             (0x16, 9, "current_ac_ma")):
        for emu in (baseline, candidate):
            emu.frame(ack_packet(mode)); emu.run(seconds=0.8)
            emu.frame(reading_packet("12.34", unit)); emu.run(seconds=1.5)
        baseline_measurement = measurement_region_sha256(baseline)
        candidate_measurement = measurement_region_sha256(candidate)
        symbol_checks.append({
            "mode": name,
            "measurement_region_equal_to_v2_baseline":
                baseline_measurement == candidate_measurement,
            "candidate_measurement_region_sha256": candidate_measurement,
            "comparison_excludes_dynamic_battery_bar_y_0_19": True,
        })
    candidate.panel.save(PACKAGE / "emulacja-bezpieczna-symbole-pomiary.png")

    ranges = binary_diff_ranges()
    healthy = all(item["fault"] is None and not item["halted"]
                  and item["main_loop_entered"]
                  for item in (default_state, english_state, theme_state,
                               thresholds_state, history_state,
                               polish_charging_state, english_charging_state))
    default_polish = default_state["stored_language"] == 2 \
        and default_state["resource_prefix"] == "menu/german/"
    english_available = english_state["stored_language"] == 1 \
        and english_state["resource_prefix"] == "menu/english/"
    theme1_only = theme_state["stored_layout"] == 0
    symbols_unchanged = all(x["measurement_region_equal_to_v2_baseline"]
                            for x in symbol_checks)
    polish_charging_replaced = (
        polish_charging.panel.checksum() != polish_charging_baseline.panel.checksum()
    )
    english_charging_unchanged = (
        english_charging.panel.checksum() == english_charging_baseline.panel.checksum()
    )
    confined = binary_changes_confined()
    no_extra_writes = state(candidate)["w25q_erases"] == state(baseline)["w25q_erases"] \
        and state(candidate)["w25q_programs"] == state(baseline)["w25q_programs"]
    passed = healthy and default_polish and english_available and theme1_only \
        and symbols_unchanged and polish_charging_replaced \
        and english_charging_unchanged and confined and no_extra_writes
    report = {
        "definition": "Polish default, English second, Theme1, stock symbols, Polish charging warning",
        "pass": passed,
        "scope": "RV32 emulator and byte confinement; physical display still requires confirmation",
        "firmware": str(FIRMWARE),
        "firmware_sha256": hashlib.sha256(FIRMWARE.read_bytes()).hexdigest().upper(),
        "healthy": healthy,
        "default_polish": default_polish,
        "english_second_available": english_available,
        "theme1_locked": theme1_only,
        "stock_symbols_unchanged": symbols_unchanged,
        "polish_charging_caption_replaced": polish_charging_replaced,
        "english_charging_caption_unchanged": english_charging_unchanged,
        "binary_changes_confined_to_charging_screen": confined,
        "changed_ranges": ranges,
        "no_patch_specific_extra_w25q_writes": no_extra_writes,
        "default_boot": default_state,
        "after_english_selection": english_state,
        "after_theme2_attempt": theme_state,
        "polish_thresholds_screen": thresholds_state,
        "polish_history_screen": history_state,
        "polish_charging_screen": polish_charging_state,
        "english_charging_screen": english_charging_state,
        "symbol_checks": symbol_checks,
        "withdrawn_firmware_sha256":
            "38F5160F60F718B9F2120FCF03655BB07F590D01526A5B2720E146A8527C44F1",
    }
    (PACKAGE / "PL_EN_SYMBOLS_THEME1_VALIDATION.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()

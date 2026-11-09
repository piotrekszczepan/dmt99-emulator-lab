#!/usr/bin/env python3
"""Validate DMT-99 V5 with a firmware-rendered Polish Theme 2 menu."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE if (HERE / "DMT99_V2.4_PL").exists() else HERE.parent
RESEARCH = Path(os.environ.get(
    "DMT99_RESEARCH_DIR",
    ROOT / "dmt99-research" if (ROOT / "dmt99-research").exists()
    else ROOT / "vendor" / "dmt99-research",
))
PACKAGE = Path(os.environ.get(
    "DMT99_IMAGES_DIR",
    ROOT / "DMT99_V2.4_PL" if (ROOT / "DMT99_V2.4_PL").exists()
    else ROOT / "images",
))
sys.path[:0] = [str(RESEARCH / ".deps"), str(RESEARCH / "tools")]

from fw_emulator import Ch32Emulator
from test_firmware_emulation import ack_packet, battery_raw, reading_packet, settings_image


FIRMWARE = PACKAGE / "DMT-99_V2.4_PL_EN_THEME2_PL_V5.BIN"
BASELINE = PACKAGE / "DMT-99_V2.4_PL_EN_SYMBOLS_THEME1_THEME2_V4.BIN"
STOCK_FLASH = RESEARCH / "flashdump" / "dmt99_flash_1.bin"
LOAD = 0x6400
PINS = {1: "PC10", 2: "PC11", 3: "PC9", 4: "PC12", 5: "PC8", 6: "PC8"}
HOOK = 0x27400
CALL_SITES = (
    0x16ACC, 0x16AF0, 0x16B3E, 0x16B66, 0x16B8E,
    0x16F5E, 0x16F84, 0x16FBC, 0x16FE4, 0x1700C,
    0x172AC, 0x172D2, 0x1730C, 0x1739C,
    0x1794C, 0x17972, 0x17A26, 0x17A86, 0x17AAC,
)
PAGE_SEQUENCES = {
    "menu": (6,),
    "progi": (6, 1, 3),
    "historia": (6, 1, 1, 3),
    "system": (6, 1, 1, 1, 3),
    "reset": (6, 1, 1, 1, 1, 3),
    "informacje": (6, 1, 1, 1, 1, 1, 3),
}


def make(firmware: Path = FIRMWARE, *, language: int | None = 2,
         layout: int = 0) -> Ch32Emulator:
    fixture = None if language is None else settings_image(
        view=1, layout=layout, english=language
    )
    emu = Ch32Emulator(
        original=True,
        bin_path=firmware,
        flash_dump=STOCK_FLASH,
        settings=fixture,
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


def measurement_hash(emu: Ch32Emulator) -> str:
    image = emu.panel.image().crop((0, 20, 320, 240))
    return hashlib.sha256(image.tobytes()).hexdigest()


def open_system(emu: Ch32Emulator) -> None:
    for key in (6, 1, 1, 1, 3):
        press(emu, key)


def binary_diff_ranges() -> list[dict]:
    base, candidate = BASELINE.read_bytes(), FIRMWARE.read_bytes()
    changed = [
        index for index in range(max(len(base), len(candidate)))
        if (base[index] if index < len(base) else None)
        != (candidate[index] if index < len(candidate) else None)
    ]
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
    allowed = tuple(range(site - LOAD, site - LOAD + 4) for site in CALL_SITES)
    return all(
        index >= len(base) or any(index in region for region in allowed)
        for index in range(max(len(base), len(candidate)))
        if (base[index] if index < len(base) else None)
        != (candidate[index] if index < len(candidate) else None)
    )


def capture_page(firmware: Path, sequence: tuple[int, ...], *, language: int,
                 layout: int) -> tuple[Ch32Emulator, str]:
    emu = make(firmware, language=language, layout=layout)
    for key in sequence:
        press(emu, key)
    return emu, emu.panel.checksum()


def render_reading(emu: Ch32Emulator, mode: int, unit: int) -> None:
    emu.frame(ack_packet(mode))
    emu.run(seconds=0.8)
    emu.frame(reading_packet("12.34", unit))
    emu.run(seconds=1.5)


def main() -> None:
    print("[1/7] rozruch domyslny", flush=True)
    default = make(language=None)
    default_state = state(default)

    page_checks = []
    page_states = []
    for name, sequence in PAGE_SEQUENCES.items():
        baseline_page, baseline_hash = capture_page(
            BASELINE, sequence, language=2, layout=1
        )
        candidate_page, candidate_hash = capture_page(
            FIRMWARE, sequence, language=2, layout=1
        )
        candidate_page.panel.save(PACKAGE / f"emulacja-v5-motyw2-{name}.png")
        candidate_state = state(candidate_page)
        page_states.append(candidate_state)
        page_checks.append({
            "page": name,
            "different_from_german_v4": candidate_hash != baseline_hash,
            "candidate_framebuffer_sha256": candidate_hash,
            "baseline_framebuffer_sha256": baseline_hash,
            "healthy": candidate_state["fault"] is None
            and not candidate_state["halted"]
            and candidate_state["main_loop_entered"],
        })
        print(f"[2/7] strona PL Motyw 2: {name}", flush=True)

    theme1_baseline, theme1_baseline_hash = capture_page(
        BASELINE, PAGE_SEQUENCES["menu"], language=2, layout=0
    )
    theme1, theme1_hash = capture_page(
        FIRMWARE, PAGE_SEQUENCES["menu"], language=2, layout=0
    )
    theme1_state = state(theme1)
    theme1.panel.save(PACKAGE / "emulacja-v5-motyw1-menu.png")
    print("[3/7] Motyw 1", flush=True)

    english_checks = []
    english_states = []
    for name in ("menu", "progi", "system"):
        sequence = PAGE_SEQUENCES[name]
        baseline_page, baseline_hash = capture_page(
            BASELINE, sequence, language=1, layout=1
        )
        candidate_page, candidate_hash = capture_page(
            FIRMWARE, sequence, language=1, layout=1
        )
        english_states.append(state(candidate_page))
        english_checks.append({
            "page": name,
            "unchanged": candidate_hash == baseline_hash,
            "framebuffer_sha256": candidate_hash,
        })
        print(f"[4/7] strona EN Motyw 2: {name}", flush=True)

    selected_theme2 = make(language=2, layout=0)
    open_system(selected_theme2)
    for key in (1, 5):
        press(selected_theme2, key)
    selected_theme2_state = state(selected_theme2)
    selected_theme2.panel.save(PACKAGE / "emulacja-v5-wybrany-motyw2.png")
    print("[5/7] wybor Motywu 2", flush=True)

    polish_charging_baseline = make(BASELINE, language=2, layout=1)
    polish_charging_baseline.charging = True
    polish_charging_baseline.run(seconds=2.5)
    polish_charging = make(language=2, layout=1)
    polish_charging.charging = True
    polish_charging.run(seconds=2.5)
    polish_charging_state = state(polish_charging)
    polish_charging.panel.save(PACKAGE / "emulacja-v5-ladowanie-pl.png")

    english_charging_baseline = make(BASELINE, language=1, layout=1)
    english_charging_baseline.charging = True
    english_charging_baseline.run(seconds=2.5)
    english_charging = make(language=1, layout=1)
    english_charging.charging = True
    english_charging.run(seconds=2.5)
    english_charging_state = state(english_charging)
    print("[6/7] ekrany ladowania", flush=True)

    symbol_checks = []
    for layout in (0, 1):
        for mode, unit, name in (
            (0x0C, 6, "voltage_dc"),
            (0x0F, 18, "frequency"),
            (0x16, 9, "current_ac_ma"),
        ):
            baseline = make(BASELINE, language=2, layout=layout)
            candidate = make(language=2, layout=layout)
            render_reading(baseline, mode, unit)
            render_reading(candidate, mode, unit)
            symbol_checks.append({
                "layout": layout,
                "mode": name,
                "measurement_region_equal_to_pre_charging_patch_baseline":
                    measurement_hash(baseline) == measurement_hash(candidate),
                "comparison_excludes_dynamic_battery_bar_y_0_19": True,
            })
            print(f"[7/7] pomiar layout={layout} mode={name}", flush=True)

    all_states = [
        default_state, theme1_state, selected_theme2_state,
        polish_charging_state, english_charging_state,
        *page_states, *english_states,
    ]
    healthy = all(
        item["fault"] is None and not item["halted"] and item["main_loop_entered"]
        for item in all_states
    )
    default_polish = (
        default_state["stored_language"] == 2
        and default_state["resource_prefix"] == "menu/german/"
    )
    both_themes = theme1_state["stored_layout"] == 0 \
        and selected_theme2_state["stored_layout"] == 1
    symbols_unchanged = all(
        item["measurement_region_equal_to_pre_charging_patch_baseline"]
        for item in symbol_checks
    )
    charging_polish = polish_charging.panel.checksum() == polish_charging_baseline.panel.checksum()
    charging_english = english_charging.panel.checksum() == english_charging_baseline.panel.checksum()
    polish_pages = all(
        item["different_from_german_v4"] and item["healthy"]
        for item in page_checks
    )
    theme1_unchanged = theme1_hash == theme1_baseline_hash
    english_unchanged = all(item["unchanged"] for item in english_checks)
    no_extra_writes = all(
        item["w25q_erases"] == theme1_state["w25q_erases"]
        and item["w25q_programs"] == theme1_state["w25q_programs"]
        for item in all_states
    )
    confined = binary_changes_confined()
    all_call_sites_changed = all(
        BASELINE.read_bytes()[site - LOAD:site - LOAD + 4]
        != FIRMWARE.read_bytes()[site - LOAD:site - LOAD + 4]
        for site in CALL_SITES
    )
    passed = (
        healthy and default_polish and both_themes and polish_pages
        and theme1_unchanged and english_unchanged and symbols_unchanged
        and charging_polish and charging_english and no_extra_writes
        and confined and all_call_sites_changed
    )
    report = {
        "definition": "Polish default, English second, Polish Theme 1 and firmware-rendered Polish Theme 2",
        "pass": passed,
        "scope": "RV32 emulator and byte confinement; V5 Theme 2 still requires physical-display confirmation",
        "firmware": str(FIRMWARE),
        "firmware_sha256": hashlib.sha256(FIRMWARE.read_bytes()).hexdigest().upper(),
        "healthy": healthy,
        "default_polish": default_polish,
        "theme1_and_theme2_selectable": both_themes,
        "polish_theme2_pages_replaced": polish_pages,
        "theme1_unchanged_from_v4": theme1_unchanged,
        "english_theme2_unchanged_from_v4": english_unchanged,
        "stock_measurement_rendering_unchanged_from_v4_in_both_themes": symbols_unchanged,
        "polish_charging_screen_unchanged_from_working_v4": charging_polish,
        "english_charging_caption_unchanged": charging_english,
        "no_patch_specific_extra_w25q_writes": no_extra_writes,
        "binary_changes_confined_to_menu_call_sites_and_appended_patch": confined,
        "all_expected_call_sites_changed": all_call_sites_changed,
        "changed_ranges": binary_diff_ranges(),
        "default_boot": default_state,
        "theme1": theme1_state,
        "theme2_selected_in_menu": selected_theme2_state,
        "polish_charging_theme2": polish_charging_state,
        "english_charging_theme2": english_charging_state,
        "polish_theme2_pages": page_checks,
        "english_theme2_pages": english_checks,
        "symbol_checks": symbol_checks,
    }
    (PACKAGE / "PL_THEME2_VALIDATION.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()

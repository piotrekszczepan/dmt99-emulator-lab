#!/usr/bin/env python3
"""DMT-99 Emulator Lab - local GUI for exercising V2.4-compatible firmware."""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
WORKSPACE = APP_DIR.parent
RESEARCH = Path(os.environ.get("DMT99_RESEARCH_DIR", APP_DIR / "vendor" / "dmt99-research"))
if not (RESEARCH / "tools" / "fw_emulator.py").is_file():
    RESEARCH = WORKSPACE / "dmt99-research"
PACKAGE = Path(os.environ.get("DMT99_IMAGES_DIR", WORKSPACE / "DMT99_V2.4_PL"))
sys.path[:0] = [str(RESEARCH / ".deps"), str(RESEARCH / "tools")]

from PIL import Image, ImageTk
try:
    from fw_emulator import Ch32Emulator
    from test_firmware_emulation import ack_packet, battery_raw, reading_packet, settings_image
except ImportError as exc:
    raise SystemExit(
        "Brak silnika emulacji. Uruchom najpierw setup.bat albo ustaw "
        "DMT99_RESEARCH_DIR na katalog dmt-99-multimeter-custom-firmware."
    ) from exc


DEFAULT_FW = PACKAGE / "DMT-99_V2.4_20240306_PL_CODE.BIN"
if not DEFAULT_FW.is_file():
    DEFAULT_FW = PACKAGE / "DMT-99_V2.4_20240306_PL.BIN"
DEFAULT_FLASH = PACKAGE / "DMT99_W25Q64_V2.4_PL_REFERENCE.bin"
if not DEFAULT_FW.is_file():
    DEFAULT_FW = APP_DIR / "images" / "DMT99_firmware.bin"
if not DEFAULT_FLASH.is_file():
    DEFAULT_FLASH = APP_DIR / "images" / "DMT99_W25Q64.bin"
STOCK_FW = RESEARCH / "DMT-99_V2.4_20240306.bin"
STOCK_FLASH = RESEARCH / "flashdump" / "dmt99_flash_1.bin"

LANGUAGES = [
    ("2 — polski (miejsce niemieckiego)", 2),
]

PROBE_MODES = [
    ("Napięcie DC [V]", 0x0C, 6),
    ("Napięcie DC [mV]", 0x0C, 7),
    ("Napięcie AC [V]", 0x0D, 6),
    ("Napięcie AC [mV]", 0x0D, 7),
    ("Prąd DC [A]", 0x10, 10),
    ("Prąd DC [mA]", 0x11, 9),
    ("Prąd DC [µA]", 0x11, 8),
    ("Prąd AC [A]", 0x15, 10),
    ("Prąd AC [mA]", 0x16, 9),
    ("Prąd AC [µA]", 0x16, 8),
]


def display_text(value: float) -> str:
    """Format a signed simulated probe value into the meter's four digits."""
    if not math.isfinite(value):
        raise ValueError("Wartość sond musi być skończoną liczbą")
    negative = value < 0
    value = abs(value)
    if value > 9999:
        raise ValueError("Maksymalna wartość wyświetlana to 9999 wybranych jednostek")
    if value >= 1000:
        text = f"{value:.0f}"
    elif value >= 100:
        text = f"{value:.1f}"
    elif value >= 10:
        text = f"{value:.2f}"
    else:
        text = f"{value:.3f}"
    digits = sum(ch.isdigit() for ch in text)
    if digits != 4:
        raise ValueError(f"Wartość {value} nie mieści się w czterech cyfrach")
    return ("-" if negative else "") + text


def emulator_state(emu: Ch32Emulator):
    try:
        settings = bytes(emu.uc.mem_read(0x20000020, 64))
        language = int.from_bytes(settings[30:32], "little") & 7
    except Exception:
        language = None
    try:
        prefix = bytes(emu.uc.mem_read(0x20000298, 48)).split(b"\0")[0].decode("ascii", "replace")
    except Exception:
        prefix = ""
    return {
        "fault": emu.fault,
        "halted": emu.halted,
        "main_loop_entered": emu.loop_entered,
        "language_index": language,
        "resource_prefix": prefix,
        "panel_commands": len(emu.panel.commands),
        "pixels": emu.panel.pixels,
        "framebuffer_sha256": emu.panel.checksum(),
        "uart_packets": [x.hex().upper() for x in emu.tx_packets],
        "flash_operations": emu.flash_ops[-20:],
        "w25q_erases": emu.nor.erases[-20:],
        "w25q_programs": emu.nor.programs[-20:],
    }


class LabApp:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk

        self.tk, self.ttk, self.root = tk, ttk, root
        self.emu = None
        self.messages = queue.Queue()
        self.busy = False
        self.photo = None
        root.title("DMT-99 Emulator Lab")
        root.minsize(1120, 760)
        root.geometry("1450x1020")

        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 18))
        style.configure("Status.TLabel", font=("Consolas", 10))

        outer = ttk.Frame(root, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="DMT-99 Emulator Lab", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Emulacja oryginalnego kodu RV32 V2.4: CH32V303, W25Q64, UART, przyciski i ST7789").pack(anchor="w", pady=(0, 10))

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, padding=(0, 0, 12, 0))
        right = ttk.Frame(body)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2, minsize=470)
        body.rowconfigure(0, weight=1)
        left.grid(row=0, column=0, sticky="nsew")
        right.grid(row=0, column=1, sticky="nsew")

        self._build_screen(left)
        self._build_controls(right)
        self._build_log(outer)
        self.root.after(100, self._poll)

    def _build_screen(self, parent):
        ttk = self.ttk
        frame = ttk.LabelFrame(parent, text="Wirtualny FNIRSI DMT-99", padding=8)
        frame.pack(fill="both", expand=True)
        self.meter = self.tk.Canvas(frame, width=620, height=710, bg="#d8d8d8",
                                   highlightthickness=0)
        self.meter.pack(anchor="center", expand=True)
        c = self.meter
        # Pionowe proporcje i układ elementów odwzorowane ze zdjęcia DMT-99.
        c.create_polygon(78,330,542,330,565,360,548,684,518,704,102,704,72,684,55,360,
                         fill="#15191d", outline="#30363b", width=4)
        for y in (410,500,590):
            c.create_polygon(58,y,78,y+13,78,y+58,58,y+45,fill="#252a2f",outline="#080a0c",width=2)
            c.create_polygon(562,y,542,y+13,542,y+58,562,y+45,fill="#252a2f",outline="#080a0c",width=2)
        c.create_polygon(87,18,533,18,568,53,568,326,523,382,97,382,52,326,52,53,
                         fill="#65a8ee", outline="#333d46", width=5)
        c.create_polygon(112,45,508,45,538,73,538,342,510,365,110,365,82,342,82,73,
                         fill="#171b20", outline="#27699d", width=3)
        c.create_text(310,35,text="FNIRSI",fill="#101820",font=("Segoe UI Semibold",18))
        c.create_rectangle(102,55,518,363,fill="#020609",outline="#354956",width=4)
        self.screen_size = (400, 300)
        self.photo = ImageTk.PhotoImage(Image.new("RGB", self.screen_size, "#05090d"))
        self.screen_item = c.create_image(110,59,anchor="nw",image=self.photo)
        self.screen_hint = c.create_text(310,209,text="Uruchom firmware",fill="#7891a3",
                                         font=("Segoe UI",16))

        self._meter_button(142,390,"⏻","PC2",.12,kind="power")
        c.create_text(488,390,text="DMT-99",anchor="e",fill="#65727b",font=("Segoe UI Semibold",12))
        self._meter_button(310,425,"HOLD\nREL","PC10",.12)
        self._meter_button(208,488,"mA\nA","PC11",.12)
        self._meter_button(310,488,"AUTO\nMENU","PC8",.12,alternate_hold=.8)
        self._meter_button(412,488,"V Ω Hz\n→","PC9",.12)
        self._meter_button(310,552,"NCV\nLIVE  ←","PC12",.12)

        for x,y,label,color in [(205,615,"10A","#138cf0"),(415,615,"V Ω Hz","#138cf0"),
                                (255,674,"mA","#138cf0"),(365,674,"COM","#111315")]:
            c.create_text(x,y-30,text=label,fill="#c7d0d6",font=("Segoe UI Semibold",10))
            c.create_oval(x-27,y-27,x+27,y+27,fill="#050708",outline="#020303",width=4)
            c.create_oval(x-15,y-15,x+15,y+15,fill=color,outline="#427baf",width=3)
            c.create_oval(x-6,y-6,x+6,y+6,fill="#030405",outline="#0a0d0f")
        self.status = self.tk.StringVar(value="Stan: emulator nieuruchomiony")
        ttk.Label(frame, textvariable=self.status, style="Status.TLabel", justify="left").pack(fill="x", pady=(10, 0))

    def _meter_button(self, x, y, label, pin, hold, kind="standard", alternate_hold=None):
        c = self.meter
        tag = f"meter_{pin}_{int(hold*100)}_{x}"
        if kind == "power":
            c.create_oval(x-37,y-22,x+37,y+22,fill="#c9d2d9",outline="#303941",width=3,tags=(tag,))
        else:
            c.create_polygon(x-43,y-30,x+34,y-30,x+45,y-18,x+39,y+25,x+25,y+32,
                             x-32,y+32,x-44,y+18,fill="#292d31",outline="#79bdff",width=3,tags=(tag,))
        c.create_text(x,y,text=label,fill="#e4edf2" if kind != "power" else "#303941",justify="center",
                      font=("Segoe UI Semibold",9),tags=(tag,))
        c.tag_bind(tag,"<Button-1>",lambda _event,p=pin,h=hold:self.press(p,h))
        if alternate_hold is not None:
            c.tag_bind(tag,"<Button-3>",lambda _event,p=pin,h=alternate_hold:self.press(p,h))

    def _row_file(self, parent, label, variable, command):
        ttk = self.ttk
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=14).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(row, text="Wybierz…", command=command).pack(side="left")

    def _build_controls(self, parent):
        ttk = self.ttk
        from tkinter import filedialog

        files = ttk.LabelFrame(parent, text="Obrazy", padding=10)
        files.pack(fill="x")
        self.firmware = self.tk.StringVar(value=str(DEFAULT_FW))
        self.flash = self.tk.StringVar(value=str(DEFAULT_FLASH))
        self._row_file(files, "Firmware BIN", self.firmware,
                       lambda: self._choose(self.firmware, [("BIN", "*.bin"), ("Wszystkie", "*.*")]))
        self._row_file(files, "W25Q64", self.flash,
                       lambda: self._choose(self.flash, [("BIN", "*.bin"), ("Wszystkie", "*.*")]))

        boot = ttk.LabelFrame(parent, text="Uruchomienie", padding=10)
        boot.pack(fill="x", pady=(10, 0))
        self.erased = self.tk.BooleanVar(value=True)
        ttk.Checkbutton(boot, text="Skasowane ustawienia / pierwszy start", variable=self.erased).pack(anchor="w")
        row = ttk.Frame(boot); row.pack(fill="x", pady=4)
        ttk.Label(row, text="Język startowy", width=17).pack(side="left")
        self.language = self.tk.StringVar(value=LANGUAGES[0][0])
        ttk.Combobox(row, textvariable=self.language, values=[x[0] for x in LANGUAGES], state="readonly").pack(side="left", fill="x", expand=True)
        row = ttk.Frame(boot); row.pack(fill="x", pady=4)
        ttk.Label(row, text="Bateria", width=17).pack(side="left")
        self.battery = self.tk.IntVar(value=87)
        ttk.Scale(row, from_=5, to=100, variable=self.battery, orient="horizontal").pack(side="left", fill="x", expand=True)
        self.battery_label = ttk.Label(row, text="87%", width=5); self.battery_label.pack(side="left")
        self.battery.trace_add("write", lambda *_: self.battery_label.configure(text=f"{self.battery.get()}%"))
        row = ttk.Frame(boot); row.pack(fill="x", pady=(7, 0))
        self.boot_btn = ttk.Button(row, text="Uruchom (4 s)", command=self.boot)
        self.boot_btn.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Restart", command=self.boot).pack(side="left", fill="x", expand=True, padx=(6, 0))

        run = ttk.LabelFrame(parent, text="Sterowanie", padding=10)
        run.pack(fill="x", pady=(10, 0))
        keyrow = ttk.Frame(run); keyrow.pack(fill="x")
        keys = [
            ("▲ Poprzedni", "PC10", .12), ("▼ Następny", "PC11", .12),
            ("Wejdź", "PC9", .12), ("Wstecz", "PC12", .12),
            ("Zatwierdź", "PC8", .12), ("Menu / wyjdź", "PC8", .8),
            ("Wyłącz miernik", "PC2", .12),
        ]
        for i, (label, pin, hold) in enumerate(keys):
            ttk.Button(keyrow, text=label, command=lambda p=pin, h=hold: self.press(p, h)).grid(row=i // 3, column=i % 3, sticky="ew", padx=2, pady=2)
        for i in range(3): keyrow.columnconfigure(i, weight=1)
        ttk.Label(
            run,
            text="Menu: HOLD/REL = poprzedni  •  mA/A = następny  •  VΩHz = wejdź\n"
                 "NCV/LIVE = wstecz  •  AUTO/MENU krótko = zatwierdź  •  długo = menu/wyjdź",
            foreground="#46545e", justify="left"
        ).pack(anchor="w", pady=(5, 0))
        row = ttk.Frame(run); row.pack(fill="x", pady=(6, 0))
        self.seconds = self.tk.StringVar(value="1.0")
        ttk.Label(row, text="Czas [s]").pack(side="left")
        ttk.Entry(row, textvariable=self.seconds, width=7).pack(side="left", padx=5)
        ttk.Button(row, text="Wykonaj", command=self.run_time).pack(side="left")
        ttk.Button(row, text="Pomiar 12.34 V", command=self.demo_reading).pack(side="left", padx=(6, 0))

        probes = ttk.LabelFrame(parent, text="Sondy pomiarowe — sygnał symulowany", padding=10)
        probes.pack(fill="x", pady=(10, 0))
        row = ttk.Frame(probes); row.pack(fill="x")
        self.probe_mode = self.tk.StringVar(value=PROBE_MODES[0][0])
        ttk.Combobox(row, textvariable=self.probe_mode,
                     values=[x[0] for x in PROBE_MODES], state="readonly").pack(side="left", fill="x", expand=True)
        self.probe_value = self.tk.StringVar(value="12.34")
        ttk.Entry(row, textvariable=self.probe_value, width=10, font=("Consolas", 10)).pack(side="left", padx=(6, 0))
        ttk.Button(probes, text="Podaj wartość na sondy", command=self.apply_probes).pack(fill="x", pady=(5, 0))
        ttk.Label(probes, text="To wejście cyfrowe ASIC→MCU; nie emuluje fizycznego toru analogowego.",
                  foreground="#7a4d00").pack(anchor="w", pady=(4, 0))

        packet = ttk.LabelFrame(parent, text="Ramka UART — dokładnie 13 bajtów hex", padding=10)
        packet.pack(fill="x", pady=(10, 0))
        self.packet = self.tk.StringVar(value="5A A5 FD 0C 00 00 00 00 00 00 00 00 00")
        ttk.Entry(packet, textvariable=self.packet, font=("Consolas", 9)).pack(fill="x")
        ttk.Button(packet, text="Wyślij ramkę i wykonaj 1,5 s", command=self.send_packet).pack(fill="x", pady=(5, 0))

        tests = ttk.LabelFrame(parent, text="Testy", padding=10)
        tests.pack(fill="x", pady=(10, 0))
        ttk.Button(tests, text="Szybki test bieżącego firmware", command=self.quick_test).pack(fill="x")
        ttk.Button(tests, text="Regresja angielska: oryginał ↔ bieżący", command=self.english_regression).pack(fill="x", pady=(5, 0))
        ttk.Button(tests, text="Zapisz zrzut PNG…", command=self.save_png).pack(fill="x", pady=(5, 0))
        ttk.Button(tests, text="Krótka instrukcja", command=self.show_help).pack(fill="x", pady=(5, 0))

    def _build_log(self, parent):
        ttk = self.ttk
        box = ttk.LabelFrame(parent, text="Dziennik", padding=6)
        box.pack(fill="x", pady=(10, 0))
        self.log = self.tk.Text(box, height=7, bg="#10161c", fg="#d7e2ea",
                                insertbackground="white", font=("Consolas", 9), wrap="word")
        self.log.pack(fill="x")
        self._log("Gotowe. Emulacja V2.4 jest instrukcyjna i może potrzebować kilkunastu sekund na 4 s czasu wirtualnego.")

    def _choose(self, variable, types):
        from tkinter import filedialog
        value = filedialog.askopenfilename(filetypes=types, initialdir=str(Path(variable.get()).parent))
        if value: variable.set(value)

    def _log(self, message):
        stamp = time.strftime("%H:%M:%S")
        self.log.insert("end", f"[{stamp}] {message}\n")
        self.log.see("end")

    def _task(self, label, function):
        if self.busy:
            self._log("Emulator jest zajęty.")
            return
        self.busy = True
        self.status.set(f"Stan: {label}…")
        self._log(label)
        def worker():
            try:
                result = function()
                self.messages.put(("ok", label, result))
            except Exception:
                self.messages.put(("error", label, traceback.format_exc()))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, label, payload = self.messages.get_nowait()
                self.busy = False
                if kind == "error":
                    self.status.set("Stan: BŁĄD")
                    self._log(payload)
                else:
                    self._finish(label, payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _finish(self, label, payload):
        if isinstance(payload, dict) and payload.get("image") is not None:
            image = payload.pop("image")
            shown = image.resize(self.screen_size, Image.Resampling.NEAREST)
            self.photo = ImageTk.PhotoImage(shown)
            self.meter.itemconfigure(self.screen_item, image=self.photo)
            self.meter.itemconfigure(self.screen_hint, state="hidden")
        state = payload.get("state", payload) if isinstance(payload, dict) else {}
        if isinstance(state, dict) and "framebuffer_sha256" in state:
            self.status.set(
                f"fault={state['fault']} | halted={state['halted']} | loop={state['main_loop_entered']}\n"
                f"language={state['language_index']} | path={state['resource_prefix']} | "
                f"pixels={state['pixels']}\nsha={state['framebuffer_sha256']}"
            )
        else:
            self.status.set(f"Stan: {label} zakończony")
        self._log(payload.get("summary", "Zakończono."))

    def _paths(self):
        fw, flash = Path(self.firmware.get()), Path(self.flash.get())
        if not fw.is_file(): raise FileNotFoundError(f"Brak firmware: {fw}")
        if not flash.is_file(): raise FileNotFoundError(f"Brak W25Q64: {flash}")
        if flash.stat().st_size != 8 * 1024 * 1024:
            raise ValueError(f"W25Q64 musi mieć 8 MiB, ma {flash.stat().st_size} B")
        return fw, flash

    def _settings(self):
        if self.erased.get(): return None
        label = self.language.get()
        index = next(value for text, value in LANGUAGES if text == label)
        return settings_image(view=1, english=index)

    def _snapshot(self, summary=""):
        state = emulator_state(self.emu)
        return {"image": self.emu.panel.image(), "state": state,
                "summary": summary or json.dumps(state, ensure_ascii=False)}

    def boot(self):
        def action():
            fw, flash = self._paths()
            self.emu = Ch32Emulator(original=True, bin_path=fw, flash_dump=flash,
                                    settings=self._settings(), battery_raw=battery_raw(self.battery.get()))
            self.emu.run(seconds=4)
            return self._snapshot("Firmware uruchomiony; stan ekranu i CPU odświeżony.")
        self._task("Uruchamianie firmware", action)

    def _require(self):
        if self.emu is None: raise RuntimeError("Najpierw uruchom firmware.")

    def run_time(self):
        def action():
            self._require(); seconds = float(self.seconds.get())
            if not 0 < seconds <= 30: raise ValueError("Czas musi być w zakresie 0–30 s")
            self.emu.run(seconds=seconds)
            return self._snapshot(f"Wykonano {seconds:g} s czasu wirtualnego.")
        self._task("Wykonywanie kodu", action)

    def press(self, pin, hold):
        def action():
            self._require(); self.emu.press(pin, hold=hold); self.emu.run(seconds=1.5)
            return self._snapshot(f"Przycisk {pin}, przytrzymanie {hold:g} s.")
        self._task(f"Przycisk {pin}", action)

    def send_packet(self):
        def action():
            self._require()
            raw = bytes.fromhex(self.packet.get())
            if len(raw) != 13: raise ValueError(f"Ramka musi mieć 13 bajtów, ma {len(raw)}")
            self.emu.frame(raw); self.emu.run(seconds=1.5)
            return self._snapshot(f"Wysłano UART: {raw.hex(' ').upper()}")
        self._task("Wysyłanie UART", action)

    def demo_reading(self):
        def action():
            self._require()
            self.emu.frame(reading_packet("12.34", 6)); self.emu.run(seconds=1.5)
            return self._snapshot("Wysłano symulowany pomiar 12.34 V.")
        self._task("Symulowany pomiar", action)

    def apply_probes(self):
        def action():
            self._require()
            label = self.probe_mode.get()
            _, mode, unit = next(item for item in PROBE_MODES if item[0] == label)
            value = float(self.probe_value.get().replace(",", "."))
            text = display_text(value)
            command = ack_packet(mode)
            reading = reading_packet(text, unit)
            self.emu.frame(command); self.emu.run(seconds=.8)
            self.emu.frame(reading); self.emu.run(seconds=1.5)
            return self._snapshot(
                f"Sondy: {label} = {value:g}; ekran={text}; "
                f"ACK={command.hex(' ').upper()}; DATA={reading.hex(' ').upper()}"
            )
        self._task("Podawanie wartości na sondy", action)

    def quick_test(self):
        def action():
            fw, flash = self._paths()
            emu = Ch32Emulator(original=True, bin_path=fw, flash_dump=flash,
                               settings=self._settings(), battery_raw=battery_raw(self.battery.get()))
            emu.run(seconds=4)
            emu.frame(reading_packet("12.34", 6)); emu.run(seconds=1.5)
            self.emu = emu
            state = emulator_state(emu)
            passed = state["fault"] is None and not state["halted"] and state["main_loop_entered"]
            report = {"test": "quick", "pass": passed, "state": state}
            self._save_report(report)
            result = self._snapshot(f"Szybki test: {'PASS' if passed else 'FAIL'}; raport zapisany.")
            result["test"] = report
            return result
        self._task("Szybki test", action)

    def english_regression(self):
        def action():
            fw, flash = self._paths(); fixture = settings_image(view=1, english=1)
            stock = Ch32Emulator(original=True, bin_path=STOCK_FW, flash_dump=STOCK_FLASH,
                                 settings=fixture, battery_raw=battery_raw(87))
            stock.run(seconds=4)
            candidate = Ch32Emulator(original=True, bin_path=fw, flash_dump=flash,
                                     settings=fixture, battery_raw=battery_raw(87))
            candidate.run(seconds=4)
            a, b = emulator_state(stock), emulator_state(candidate)
            passed = a["fault"] is None and b["fault"] is None and \
                     a["framebuffer_sha256"] == b["framebuffer_sha256"] and \
                     a["uart_packets"] == b["uart_packets"]
            report = {"test": "english_regression", "pass": passed, "stock": a, "candidate": b}
            self._save_report(report)
            self.emu = candidate
            result = self._snapshot(f"Regresja angielska: {'PASS' if passed else 'FAIL'}; raport zapisany.")
            result["test"] = report
            return result
        self._task("Regresja angielska", action)

    def _save_report(self, report):
        folder = APP_DIR / "raporty"; folder.mkdir(exist_ok=True)
        name = time.strftime("%Y%m%d-%H%M%S") + "-" + report["test"] + ".json"
        (folder / name).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def save_png(self):
        from tkinter import filedialog
        if self.emu is None:
            self._log("Najpierw uruchom firmware."); return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")], initialdir=str(APP_DIR))
        if path:
            self.emu.panel.save(path); self._log(f"Zapisano PNG: {path}")

    def show_help(self):
        from tkinter import messagebox
        messagebox.showinfo(
            "DMT-99 Emulator Lab — instrukcja",
            "1. Wskaż firmware BIN i obraz W25Q64.\n"
            "2. Wybierz pierwszy start albo zapisany język i kliknij Uruchom.\n"
            "3. Sterowanie menu:\n"
            "   HOLD/REL = poprzednia pozycja; mA/A = następna;\n"
            "   VΩHz = wejdź; NCV/LIVE = wstecz;\n"
            "   AUTO/MENU krótko = zatwierdź; długo = otwórz lub wyjdź.\n"
            "   Osobny przycisk zasilania wyłącza emulowany miernik.\n"
            "4. W sekcji Sondy wybierz napięcie lub prąd, wpisz wartość i kliknij "
            "Podaj wartość na sondy.\n"
            "5. Surowe ramki ASIC można wysyłać w sekcji UART.\n"
            "6. Szybki test sprawdza start i pomiar; regresja angielska porównuje ekran "
            "i UART z oryginalnym V2.4.\n"
            "7. Zapisz zrzut PNG, gdy chcesz udokumentować konkretny ekran.\n\n"
            "Emulator nie sprawdza fizycznej dokładności ani zabezpieczeń wejścia."
        )


def headless_self_test(output: Path):
    emu = Ch32Emulator(original=True, bin_path=DEFAULT_FW, flash_dump=DEFAULT_FLASH,
                       settings=None, battery_raw=battery_raw(87))
    emu.run(seconds=4)
    boot_sha = emu.panel.checksum()
    emu.frame(ack_packet(0x0C)); emu.run(seconds=.8)
    emu.frame(reading_packet(display_text(12.34), 6)); emu.run(seconds=1.5)
    state = emulator_state(emu)
    state["probe_test"] = {
        "type": "Napięcie DC [V]", "value": 12.34,
        "boot_framebuffer_sha256": boot_sha,
        "measurement_framebuffer_changed": state["framebuffer_sha256"] != boot_sha,
    }
    state["pass"] = state["fault"] is None and not state["halted"] and \
                    state["main_loop_entered"] and state["language_index"] == 2 and \
                    state["resource_prefix"] == "menu/german/" and \
                    state["probe_test"]["measurement_framebuffer_changed"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    emu.panel.save(output.with_suffix(".png"))
    print(json.dumps(state, indent=2, ensure_ascii=False))
    return 0 if state["pass"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", type=Path, help="headless boot test; writes JSON and PNG")
    args = parser.parse_args()
    if args.self_test:
        return headless_self_test(args.self_test)
    import tkinter as tk
    root = tk.Tk()
    LabApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


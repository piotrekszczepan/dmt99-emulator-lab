#!/usr/bin/env python3
"""Open-source Windows GUI for building the Polish DMT-99 V2.4 firmware.

The application never contains or downloads FNIRSI firmware.  The user must
select their own verified stock V2.4 image.  Patches are applied in a
temporary directory and the final image is published atomically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable


APP_NAME = "DMT-99 Spolszczenie"
APP_VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "tools"

STOCK_SIZE = 135_096
STOCK_SHA256 = "4BEFDF6B58E063F03901F190000D790E60D20D0A23E5EEB2B6F6840F1830E98E"
FINAL_SIZE = 140_061
FINAL_SHA256 = "F312161A6DE079A41ED18981EB8EFDDCEA6FEE410DD9F1F34350B0E688F522DA"
UPDATE_NAME = "DMT-99_V2.4_20240306.BIN"
RECOVERY_NAME = "DMT-99_V2.4_20240306.bin"

PATCH_CHAIN = (
    ("01_polish_boot", "patch_dmt99_polish_boot.py"),
    ("02_polish_language", "patch_dmt99_chinese_to_polish.py"),
    ("03_polish_charging", "patch_dmt99_polish_charging_text.py"),
    ("04_polish_theme2_v8", "patch_dmt99_polish_theme2.py"),
)

Progress = Callable[[str], None]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def validate_source(source: Path) -> None:
    if not source.is_file():
        raise ValueError("Nie znaleziono wybranego pliku firmware.")
    size = source.stat().st_size
    digest = sha256(source)
    if size != STOCK_SIZE or digest != STOCK_SHA256:
        raise ValueError(
            "To nie jest zweryfikowany oryginalny DMT-99 V2.4.\n"
            f"Rozmiar: {size} B (oczekiwano {STOCK_SIZE} B)\n"
            f"SHA-256: {digest}\n"
            f"Oczekiwano: {STOCK_SHA256}"
        )


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=destination.name + ".", suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        shutil.copyfile(source, temporary_path)
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def run_patch(script: Path, source: Path, output: Path, manifest: Path) -> None:
    if not script.is_file():
        raise FileNotFoundError(f"Brak narzedzia: {script}")
    completed = subprocess.run(
        [
            sys.executable, str(script), str(source), str(output),
            "--manifest", str(manifest),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        details = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"Etap {script.name} zakonczyl sie bledem ({completed.returncode}).\n"
            f"{details}"
        )


def build_polish_firmware(
    source: Path,
    output_root: Path,
    *,
    overwrite: bool = False,
    progress: Progress | None = None,
) -> dict:
    source = source.expanduser().resolve()
    output_root = output_root.expanduser().resolve()
    notify = progress or (lambda _message: None)

    notify("Sprawdzanie oryginalnego firmware V2.4...")
    validate_source(source)

    update_path = output_root / "DO_WGRANIA" / UPDATE_NAME
    recovery_path = output_root / "ODZYSKIWANIE" / RECOVERY_NAME
    documentation = output_root / "DOKUMENTACJA"
    manifest_path = output_root / "MANIFEST.json"

    destinations = (update_path, recovery_path, manifest_path)
    if source in {path.resolve() for path in (update_path, recovery_path)}:
        raise ValueError("Folder docelowy nie moze nadpisac pliku zrodlowego.")
    existing = [path for path in destinations if path.exists()]
    if existing and not overwrite:
        joined = "\n".join(str(path) for path in existing)
        raise FileExistsError(f"Pliki docelowe juz istnieja:\n{joined}")

    with tempfile.TemporaryDirectory(prefix="dmt99-pol-v8-") as temporary_name:
        temporary = Path(temporary_name)
        current = source
        stage_reports: list[dict] = []
        for index, (label, script_name) in enumerate(PATCH_CHAIN, start=1):
            notify(f"Etap {index}/{len(PATCH_CHAIN)}: {script_name}")
            stage_output = temporary / f"{label}.BIN"
            stage_manifest = temporary / f"{label}.json"
            run_patch(TOOLS / script_name, current, stage_output, stage_manifest)
            report = json.loads(stage_manifest.read_text(encoding="utf-8"))
            stage_reports.append({
                "stage": label,
                "tool": script_name,
                "size": stage_output.stat().st_size,
                "sha256": sha256(stage_output),
                "tool_report": report,
            })
            current = stage_output

        final_size = current.stat().st_size
        final_hash = sha256(current)
        if final_size != FINAL_SIZE or final_hash != FINAL_SHA256:
            raise RuntimeError(
                "Wynik nie odpowiada zweryfikowanej wersji V8. Nie zapisano pliku.\n"
                f"Rozmiar: {final_size} B; SHA-256: {final_hash}"
            )

        notify("Zapisywanie firmware, kopii ratunkowej i dokumentacji...")
        atomic_copy(current, update_path)
        atomic_copy(source, recovery_path)
        documentation.mkdir(parents=True, exist_ok=True)
        for stage in stage_reports:
            report_file = documentation / f"{stage['stage']}.json"
            report_file.write_text(
                json.dumps(stage, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    manifest = {
        "application": APP_NAME,
        "application_version": APP_VERSION,
        "license": "MIT",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model": "FNIRSI DMT-99",
        "base_version": "V2.4",
        "source": {
            "user_supplied": True,
            "size": STOCK_SIZE,
            "sha256": STOCK_SHA256,
        },
        "update": {
            "path": str(update_path.relative_to(output_root)).replace("\\", "/"),
            "size": FINAL_SIZE,
            "sha256": FINAL_SHA256,
        },
        "recovery": {
            "path": str(recovery_path.relative_to(output_root)).replace("\\", "/"),
            "sha256": STOCK_SHA256,
        },
        "patch_stages": [
            {key: value for key, value in stage.items() if key != "tool_report"}
            for stage in stage_reports
        ],
        "default_language": "Polski",
        "second_language": "English",
        "physical_validation_required": True,
        "bootloader_modified": False,
        "w25q64_modified": False,
        "firmware_included_with_application": False,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (documentation / "SUMY_SHA256.txt").write_text(
        f"{FINAL_SHA256}  DO_WGRANIA/{UPDATE_NAME}\n"
        f"{STOCK_SHA256}  ODZYSKIWANIE/{RECOVERY_NAME}\n",
        encoding="ascii",
    )
    (output_root / "README.txt").write_text(
        "FNIRSI DMT-99 V2.4 PL/English V8\n\n"
        f"Do wgrania: DO_WGRANIA\\{UPDATE_NAME}\n"
        f"SHA-256: {FINAL_SHA256}\n\n"
        "Nie zmieniaj nazwy pliku. Przed aktualizacja odlacz sondy od "
        "mierzonych obwodow. Oryginal ratunkowy znajduje sie w katalogu "
        "ODZYSKIWANIE. Test programowy nie zastepuje sprawdzenia na fizycznym "
        "mierniku. Ekran BOOT nalezy do oddzielnego bootloadera i nie jest "
        "modyfikowany.\n",
        encoding="utf-8",
    )
    notify("Gotowe.")
    return manifest


class PolonizerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.minsize(760, 520)

        self.source = tk.StringVar()
        self.destination = tk.StringVar()
        self.status = tk.StringVar(value="Wybierz oryginalny firmware DMT-99 V2.4.")

        frame = ttk.Frame(root, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="FNIRSI DMT-99 - tworzenie polskiego firmware V8",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            frame,
            text=(
                "Aplikacja dziala lokalnie, wymaga wlasnej oryginalnej kopii V2.4 "
                "i nie pobiera ani nie wysyla firmware."
            ),
            wraplength=700,
        ).pack(anchor="w", pady=(0, 18))

        self._path_row(
            frame, "Oryginalny plik V2.4:", self.source, self.choose_source
        )
        self._path_row(
            frame, "Folder nowej paczki:", self.destination, self.choose_destination
        )

        warning = ttk.Label(
            frame,
            text=(
                "Wynik zostanie zapisany jako DO_WGRANIA\\DMT-99_V2.4_20240306.BIN. "
                "Program zachowa tez oryginal ratunkowy. Nie podlaczaj sond do "
                "niebezpiecznego napiecia podczas aktualizacji."
            ),
            foreground="#8a3b00",
            wraplength=700,
        )
        warning.pack(anchor="w", pady=(16, 12))

        self.build_button = ttk.Button(
            frame, text="Utworz polskie firmware V8", command=self.start_build
        )
        self.build_button.pack(anchor="w", pady=(0, 12))
        ttk.Label(frame, textvariable=self.status, wraplength=700).pack(anchor="w")

        self.log = tk.Text(frame, height=12, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, pady=(10, 0))
        self.append_log("Licencja aplikacji: MIT. Firmware FNIRSI nie jest dolaczone.")

    def _path_row(
        self, parent: ttk.Frame, label: str, variable: tk.StringVar,
        command: Callable[[], None],
    ) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text=label, width=24).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        ttk.Button(row, text="Wybierz...", command=command).pack(side="right")

    def choose_source(self) -> None:
        selected = filedialog.askopenfilename(
            title="Wybierz oryginalny DMT-99 V2.4",
            filetypes=(("Firmware BIN", "*.bin *.BIN"), ("Wszystkie pliki", "*.*")),
        )
        if selected:
            self.source.set(selected)
            if not self.destination.get():
                self.destination.set(str(Path(selected).parent / "DMT99_PL_V8"))

    def choose_destination(self) -> None:
        selected = filedialog.askdirectory(title="Wybierz folder nowej paczki")
        if selected:
            self.destination.set(selected)

    def append_log(self, message: str) -> None:
        def update() -> None:
            self.log.configure(state="normal")
            self.log.insert("end", message + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
            self.status.set(message)

        self.root.after(0, update)

    def start_build(self) -> None:
        source_text = self.source.get().strip()
        destination_text = self.destination.get().strip()
        if not source_text or not destination_text:
            messagebox.showerror(APP_NAME, "Wybierz plik zrodlowy i folder docelowy.")
            return

        source = Path(source_text)
        destination = Path(destination_text)
        update_path = destination / "DO_WGRANIA" / UPDATE_NAME
        overwrite = False
        if update_path.exists():
            overwrite = messagebox.askyesno(
                APP_NAME,
                "Plik wynikowy juz istnieje. Czy zastapic poprzedni wynik i raporty?",
            )
            if not overwrite:
                return

        self.build_button.configure(state="disabled")
        self.append_log("Rozpoczynam tworzenie paczki...")

        def worker() -> None:
            try:
                manifest = build_polish_firmware(
                    source, destination, overwrite=overwrite, progress=self.append_log
                )
            except Exception as error:  # GUI boundary: display a useful message.
                self.root.after(0, lambda error=error: self.build_failed(error))
                return
            self.root.after(0, lambda: self.build_finished(destination, manifest))

        threading.Thread(target=worker, daemon=True).start()

    def build_failed(self, error: Exception) -> None:
        self.build_button.configure(state="normal")
        self.append_log(f"BLAD: {error}")
        messagebox.showerror(APP_NAME, str(error))

    def build_finished(self, destination: Path, manifest: dict) -> None:
        self.build_button.configure(state="normal")
        digest = manifest["update"]["sha256"]
        self.append_log(f"Paczka gotowa: {destination}")
        messagebox.showinfo(
            APP_NAME,
            f"Gotowe.\n\nFolder: {destination}\nSHA-256 firmware:\n{digest}",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--build", type=Path, metavar="STOCK_BIN")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.build:
        if not args.output_dir:
            raise SystemExit("--output-dir jest wymagany razem z --build")
        try:
            result = build_polish_firmware(
                args.build, args.output_dir, overwrite=args.force, progress=print
            )
        except Exception as error:
            print(f"BLAD: {error}", file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    root = tk.Tk()
    PolonizerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

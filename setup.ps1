$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Nie znaleziono Pythona. Zainstaluj Python 3.11-3.13 i uruchom ponownie."
}

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

New-Item -ItemType Directory -Force -Path vendor | Out-Null
if (-not (Test-Path -LiteralPath "vendor\dmt99-research\tools\fw_emulator.py")) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Nie znaleziono Git. Zainstaluj Git for Windows i uruchom setup ponownie."
    }
    git clone --depth 1 https://github.com/smhgzll/dmt-99-multimeter-custom-firmware.git vendor/dmt99-research
}

New-Item -ItemType Directory -Force -Path images, raporty | Out-Null
Write-Host "Gotowe. Umiesc wlasne obrazy w images albo wybierz je w aplikacji."
Write-Host "Uruchom: Uruchom_DMT99_Emulator_Lab.bat"

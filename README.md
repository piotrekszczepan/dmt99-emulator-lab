# DMT-99 Emulator Lab

Nieoficjalna aplikacja Windows do wykonywania i testowania firmware FNIRSI DMT-99 V2.4.
Interfejs przypomina prawdziwy miernik: ma ekran, przyciski funkcyjne i gniazda sond.

## Instalacja

Wymagane są Windows, Python 3.11-3.14 i Git for Windows.

1. Uruchom `setup.bat` i poczekaj na instalację zależności.
2. Uruchom `Uruchom_DMT99_Emulator_Lab.bat`.
3. Wskaż własny plik firmware BIN i obraz zewnętrznej pamięci W25Q64 o rozmiarze 8 MiB.

Repozytorium celowo nie zawiera firmowego firmware ani zrzutu pamięci FNIRSI.

## Stan wersji polskiej

Wariant z pełnymi nazwami pomiarów został wycofany: fizyczny DMT-99 ujawnił zakłócenia grafiki, których emulator nie wykrył. Zalecany wariant zachowuje fabryczne symbole, ustawia Polski jako język domyślny, pozostawia English jako drugi język i wymusza Motyw 1. Nadal wymaga potwierdzenia na fizycznym wyświetlaczu.

## Krótka instrukcja

1. Wybierz firmware i W25Q64, a następnie kliknij **Uruchom (4 s)**.
2. Sterowanie menu: **HOLD/REL** — poprzednia pozycja, **mA/A** — następna, **VΩHz** — wejdź, **NCV/LIVE** — wstecz, **AUTO/MENU krótko** — zatwierdź, **AUTO/MENU długo** — otwórz lub wyjdź. Na narysowanym AUTO/MENU prawy przycisk myszy oznacza długie naciśnięcie.
3. W sekcji **Sondy pomiarowe** wybierz napięcie/prąd AC lub DC, wpisz wartość i kliknij **Podaj wartość na sondy**.
4. **Szybki test** sprawdza start i reakcję na pomiar. **Test Polski/English** sprawdza oba języki i Motyw 1.
5. **Zapisz zrzut PNG** zapisuje aktualny ekran.

## Co jest emulowane

- instrukcje RV32 firmware V2.4 na modelu CH32V303;
- SRAM, przerwania, UART, SPI, W25Q64 i wyświetlacz ST7789;
- pięć klawiszy funkcyjnych (w tym krótki i długi AUTO/MENU), osobny przycisk zasilania PC2 oraz układ obudowy zgodny ze zdjęciem DMT-99;
- cyfrowe ramki ASIC→MCU dla napięcia i prądu DC/AC;
- start ze skasowanymi ustawieniami albo z wybranym indeksem języka i motywu;
- zapis obrazu ekranu oraz raportów JSON.

## Ograniczenia i bezpieczeństwo

- To emulator cyfrowy, nie model analogowego toru wejściowego. Nie sprawdza dokładności, kalibracji, izolacji ani zabezpieczeń miernika.
- Obsługa adresów i haków jest przygotowana dla V2.4; V2.2 wymaga osobnej mapy.
- Poprawny test w emulatorze nie dowodzi, że zmodyfikowany plik jest bezpieczny do wgrania do fizycznego urządzenia.
- Bootloader USB nie jest emulowany.
- Zależność reverse-engineeringowa jest pobierana z osobnego repozytorium; patrz `THIRD_PARTY_NOTICES.md`.

Szczegółowa tabela przycisków znajduje się w `docs/INSTRUKCJA_STEROWANIA_MENU.md`, a opis wszystkich funkcji, ograniczeń polskich znaków i oscyloskopu w `docs/INSTRUKCJA_UZYTKOWANIA_I_FUNKCJE.md`.

Narzędzia w `tools/` budują wariant Polski/English z fabrycznymi symbolami i Motywem 1. Nie zawierają firmware. Kolejność uruchamiania, ostrzeżenie o wycofanym eksperymencie oraz oczekiwane sumy zawiera `docs/BUDOWANIE_WERSJI_PL.md`.

## Test bez GUI

Po konfiguracji można uruchomić:

```powershell
.\.venv\Scripts\python.exe .\dmt99_emulator_lab.py --self-test .\raporty\self-test.json
```

## Licencja

Kod DMT-99 Emulator Lab: MIT. Licencje zależności są odrębne.

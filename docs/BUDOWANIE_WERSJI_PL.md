# Budowanie bezpieczniejszej wersji DMT-99 V2.4 PL/English

Repozytorium nie zawiera firmware FNIRSI. Potrzebna jest własna kopia `DMT-99_V2.4_20240306.bin`, 135096 bajtów, SHA-256:

`4BEFDF6B58E063F03901F190000D790E60D20D0A23E5EEB2B6F6840F1830E98E`

Zalecany proces pozostawia fabryczne symbole pomiarowe, ustawia Polski jako język domyślny, zachowuje English jako drugi język i udostępnia polski Motyw 1 oraz Motyw 2:

```powershell
python .\tools\patch_dmt99_polish_boot.py `
  .\images\DMT-99_V2.4_20240306.bin `
  .\images\DMT-99_V2.4_PL_STAGE0.BIN

python .\tools\patch_dmt99_chinese_to_polish.py `
  .\images\DMT-99_V2.4_PL_STAGE0.BIN `
  .\images\DMT-99_V2.4_PL_STAGE1.BIN

python .\tools\patch_dmt99_polish_charging_text.py `
  .\images\DMT-99_V2.4_PL_STAGE1.BIN `
  .\images\DMT-99_V2.4_PL_EN_THEME1_THEME2_V4.BIN

python .\tools\patch_dmt99_polish_theme2.py `
  .\images\DMT-99_V2.4_PL_EN_THEME1_THEME2_V4.BIN `
  .\release\DO_WGRANIA\DMT-99_V2.4_20240306.BIN
```

Oczekiwane sumy:

- `STAGE0`: `6887401AA6BCDBDE08F8BCD43C6306BB2A2EEAAD0BEE13BD266C5FF7DE222CD2`;
- `STAGE1`: `F38B3EC5EAAD6FFDE80E84216360B3C5694393492385E7AE5A85C27D506C2FAE`;
- etap V4 z polskim komunikatem ładowania i odblokowanymi motywami: `1729B0393A444E0813F523482D95572C72A382C0711D671E2AA6AB68B4C1191C`;
- wynik V5 z polskim Motywem 2: `5832E55AF2B23A78E1857500C9878FEFE7BD578278C636C5AE3E0B0C7105B9B3`.

Nie zmieniaj końcowej nazwy. Test sprzętowy z 8 listopada 2026 wykazał, że bootloader odrzucił zmodyfikowany plik nazwany `DMT-99_V2.4.BIN`, a następnie przyjął tę samą zawartość i uruchomił ją pod nazwą `DMT-99_V2.4_20240306.BIN`.

Skrypt `patch_dmt99_polish_measurement_labels.py` pozostaje wyłącznie materiałem badawczym. Wersja utworzona tym skryptem została wycofana po wykryciu zakłóceń renderowania na fizycznym mierniku. Nie należy jej wgrywać.

Motyw 2 korzysta z JPEG-ów w zewnętrznej W25Q64. Zwykły updater `BOOT` ich nie aktualizuje. V5 nie próbuje zapisywać tej pamięci: dla języka polskiego i Motywu 2 przechwytuje wyłącznie ustalone wywołania grafik menu i rysuje polskie napisy fabrycznymi funkcjami prostokąta i ASCII. Motyw 1, English, ekrany pomiarowe i kalibracja nie są zmieniane przez ten patch.

`recharge1.jpg` jest zasobem W25Q64, ale V3 nie musi go podmieniać. Dla języka polskiego omija niemiecki JPEG i wyświetla komunikat fabrycznym rendererem ASCII. Angielski JPEG, ikona ostrzeżenia i wtyczki pozostają niezmienione; skrypt nie wykonuje zapisów W25Q64.

Walidacja V5:

```powershell
$env:DMT99_IMAGES_DIR = (Resolve-Path .\images)
python .\tools\validate_dmt99_theme2.py
```

Walidator wymaga repozytorium badawczego zainstalowanego przez `setup.ps1` oraz własnego zrzutu W25Q64 w oczekiwanej lokalizacji tego repozytorium. Sprawdza sześć stron polskiego Motywu 2, niezmieniony Motyw 1 i English, ekrany ładowania, sześć przypadków pomiarowych, brak dodatkowych zapisów W25Q64 i ograniczenie zmian binarnych.

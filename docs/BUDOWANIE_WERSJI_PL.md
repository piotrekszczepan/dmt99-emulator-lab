# Budowanie bezpieczniejszej wersji DMT-99 V2.4 PL/English

Repozytorium nie zawiera firmware FNIRSI. Potrzebna jest własna kopia `DMT-99_V2.4_20240306.bin`, 135096 bajtów, SHA-256:

`4BEFDF6B58E063F03901F190000D790E60D20D0A23E5EEB2B6F6840F1830E98E`

Zalecany proces pozostawia fabryczne symbole pomiarowe, ustawia Polski jako język domyślny, zachowuje English jako drugi język i wymusza Motyw 1:

```powershell
python .\tools\patch_dmt99_polish_boot.py `
  .\images\DMT-99_V2.4_20240306.bin `
  .\images\DMT-99_V2.4_PL_STAGE0.BIN

python .\tools\patch_dmt99_chinese_to_polish.py `
  .\images\DMT-99_V2.4_PL_STAGE0.BIN `
  .\images\DMT-99_V2.4_PL_STAGE1.BIN

python .\tools\patch_dmt99_theme1_locked.py `
  .\images\DMT-99_V2.4_PL_STAGE1.BIN `
  .\images\DMT-99_V2.4_PL_EN_SYMBOLS_THEME1.BIN
```

Oczekiwane sumy:

- `STAGE0`: `6887401AA6BCDBDE08F8BCD43C6306BB2A2EEAAD0BEE13BD266C5FF7DE222CD2`;
- `STAGE1`: `CC03870190E64618630795E58B8FBB0AEA1259F101D584E5B408043333409622`;
- wynik: `12D6DE4DD46319EEE43C18A78D8EF84870366594ED18FC987B19B0B05F24628F`.

Skrypt `patch_dmt99_polish_measurement_labels.py` pozostaje wyłącznie materiałem badawczym. Wersja utworzona tym skryptem została wycofana po wykryciu zakłóceń renderowania na fizycznym mierniku. Nie należy jej wgrywać.

Motyw 2 korzysta z JPEG-ów w zewnętrznej W25Q64. Zwykły updater `BOOT` ich nie aktualizuje, dlatego bezpieczna wersja wymusza Motyw 1.

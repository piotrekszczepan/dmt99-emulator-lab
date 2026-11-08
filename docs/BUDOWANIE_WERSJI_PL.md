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
  .\images\DMT-99_V2.4_PL_EN_SYMBOLS_THEME1_V2.BIN

python .\tools\patch_dmt99_polish_charging_text.py `
  .\images\DMT-99_V2.4_PL_EN_SYMBOLS_THEME1_V2.BIN `
  .\release\DO_WGRANIA\DMT-99_V2.4_20240306.BIN
```

Oczekiwane sumy:

- `STAGE0`: `6887401AA6BCDBDE08F8BCD43C6306BB2A2EEAAD0BEE13BD266C5FF7DE222CD2`;
- `STAGE1`: `F38B3EC5EAAD6FFDE80E84216360B3C5694393492385E7AE5A85C27D506C2FAE`;
- V2 po blokadzie Motywu 1: `68568FCFBD738906C6BD63BFB3DA2FDC1D3AD11DBB5E9EE556CF20C7A8230387`;
- wynik V3 z polskim komunikatem ładowania: `C778C30CF8A83E155732EDF2C4B944CE8C1285816720692CCAEFC8A3E8F57E01`.

Nie zmieniaj końcowej nazwy. Test sprzętowy z 8 listopada 2026 wykazał, że bootloader odrzucił zmodyfikowany plik nazwany `DMT-99_V2.4.BIN`, a następnie przyjął tę samą zawartość i uruchomił ją pod nazwą `DMT-99_V2.4_20240306.BIN`.

Skrypt `patch_dmt99_polish_measurement_labels.py` pozostaje wyłącznie materiałem badawczym. Wersja utworzona tym skryptem została wycofana po wykryciu zakłóceń renderowania na fizycznym mierniku. Nie należy jej wgrywać.

Motyw 2 korzysta z JPEG-ów w zewnętrznej W25Q64. Zwykły updater `BOOT` ich nie aktualizuje, dlatego bezpieczna wersja wymusza Motyw 1.

`recharge1.jpg` jest zasobem W25Q64, ale V3 nie musi go podmieniać. Dla języka polskiego omija niemiecki JPEG i wyświetla komunikat fabrycznym rendererem ASCII. Angielski JPEG, ikona ostrzeżenia i wtyczki pozostają niezmienione; skrypt nie wykonuje zapisów W25Q64.

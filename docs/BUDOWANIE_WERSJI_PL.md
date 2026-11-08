# Budowanie wersji DMT-99 V2.4 PL

Repozytorium nie zawiera pliku firmware FNIRSI. Użytkownik musi wskazać własną, zgodną kopię `DMT-99_V2.4_20240306.bin` o rozmiarze 135096 bajtów.

Zweryfikowany SHA-256 wejścia:

`4BEFDF6B58E063F03901F190000D790E60D20D0A23E5EEB2B6F6840F1830E98E`

W katalogu głównym repozytorium wykonaj:

```powershell
python .\tools\patch_dmt99_polish_boot.py `
  .\images\DMT-99_V2.4_20240306.bin `
  .\images\DMT-99_V2.4_PL_STAGE0.BIN `
  --manifest .\raporty\stage0.json

python .\tools\patch_dmt99_chinese_to_polish.py `
  .\images\DMT-99_V2.4_PL_STAGE0.BIN `
  .\images\DMT-99_V2.4_PL_STAGE1.BIN `
  --manifest .\raporty\stage1.json

python .\tools\patch_dmt99_polish_locked.py `
  .\images\DMT-99_V2.4_PL_STAGE1.BIN `
  .\images\DMT-99_V2.4_PL_ONLY_LOCKED.BIN `
  --manifest .\raporty\locked.json

python .\tools\patch_dmt99_polish_measurement_labels.py `
  .\images\DMT-99_V2.4_PL_ONLY_LOCKED.BIN `
  .\images\DMT-99_V2.4_PL_ONLY_LABELS.BIN `
  --manifest .\raporty\labels.json
```

Oczekiwane sumy etapów:

- `STAGE0`: `6887401AA6BCDBDE08F8BCD43C6306BB2A2EEAAD0BEE13BD266C5FF7DE222CD2`;
- `STAGE1`: `CC03870190E64618630795E58B8FBB0AEA1259F101D584E5B408043333409622`;
- `LOCKED`: `C584592C44C8ADD67383053702E8F2C6CDC631F6D6E9926D0AAF29BC78FA8A50`;
- końcowy `LABELS`: `38F5160F60F718B9F2120FCF03655BB07F590D01526A5B2720E146A8527C44F1`.

Oczekiwany SHA-256 końcowego pliku:

`38F5160F60F718B9F2120FCF03655BB07F590D01526A5B2720E146A8527C44F1`

Jeżeli suma wejścia, długość albo oczekiwane bajty w punktach patchowania nie są zgodne, skrypty przerywają pracę. Nie próbuj używać ich z V2.2 ani z innym wariantem V2.4.

## Walidacja

Po `setup.bat` ustaw opcjonalnie `DMT99_IMAGES_DIR` oraz `DMT99_RESEARCH_DIR` i uruchom:

```powershell
.\.venv\Scripts\python.exe .\tools\validate_dmt99_polish_release.py
```

Do pełnego testu potrzebne są także plik etapu `LOCKED` i własny zgodny obraz W25Q64 używany przez silnik emulacji. Wynik emulatora nie jest dowodem bezpieczeństwa elektrycznego ani dokładności fizycznego miernika.

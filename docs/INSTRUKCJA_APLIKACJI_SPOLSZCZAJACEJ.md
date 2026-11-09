# DMT-99 Spolszczenie

`dmt99_polonizer.py` jest otwartozrodlowa aplikacja Windows do utworzenia polskiego firmware FNIRSI DMT-99 V2.4 V8 z legalnie posiadanej kopii oryginalnego pliku uzytkownika.

## Licencja

Kod aplikacji i narzedzi jest udostepniony na licencji MIT. Repozytorium nie zawiera i nie pobiera firmware FNIRSI ani zrzutu W25Q64.

## Uruchomienie

1. Zainstaluj Python 3.11 lub nowszy.
2. Pobierz albo sklonuj repozytorium.
3. Uruchom `Uruchom_DMT99_Spolszczenie.bat`.
4. Wskaz swoj oryginalny plik `DMT-99_V2.4_20240306.bin`.
5. Wskaz pusty folder nowej paczki.
6. Kliknij **Utworz polskie firmware V8**.

Aplikacja sprawdza rozmiar `135096` bajtow i SHA-256 oryginalu:

`4BEFDF6B58E063F03901F190000D790E60D20D0A23E5EEB2B6F6840F1830E98E`

Inny plik zostanie odrzucony bez zapisywania wyniku.

## Wynik

W wybranym folderze powstana:

- `DO_WGRANIA\DMT-99_V2.4_20240306.BIN` - polskie firmware V8;
- `ODZYSKIWANIE\DMT-99_V2.4_20240306.bin` - niezmieniony oryginal ratunkowy;
- `MANIFEST.json` - wersja, sumy i zakres zmian;
- `DOKUMENTACJA` - raporty kazdego etapu i sumy SHA-256;
- `README.txt` - krotka instrukcja wgrywania.

Oczekiwana suma wyniku V8:

`F312161A6DE079A41ED18981EB8EFDDCEA6FEE410DD9F1F34350B0E688F522DA`

## Tryb wiersza polecen

```powershell
python .\dmt99_polonizer.py `
  --build .\DMT-99_V2.4_20240306.bin `
  --output-dir .\DMT99_PL_V8
```

Opcja `--force` zezwala na zastapienie poprzedniej paczki. Plik zrodlowy nigdy nie jest nadpisywany.

## Bezpieczenstwo

- Program nie laczy sie z internetem i nie wysyla firmware.
- Wszystkie etapy wykonywane sa najpierw w katalogu tymczasowym.
- Wynik jest zapisywany dopiero po uzyskaniu dokladnej oczekiwanej sumy V8.
- Zewnetrzna pamiec W25Q64, kalibracja i bootloader nie sa modyfikowane.
- Ekran aktualizacji `BOOT` nalezy do osobnego bootloadera i pozostaje chinsko-angielski.
- Test programowy nie zastepuje sprawdzenia na fizycznym mierniku.

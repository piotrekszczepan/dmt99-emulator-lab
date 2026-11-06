# FNIRSI DMT-99 — changelog V2.2 → V2.4

## Wniosek

V2.4 jest niewielką aktualizacją istniejącego firmware, a nie nową generacją programu. Najbardziej wiarygodne zmiany dotyczą formatowania wartości i jednostek na ekranie pomiarowym oraz w historii. Z samych plików BIN nie da się uczciwie przypisać im nazw konkretnych napraw błędów, ponieważ producent nie dołączył informacji o wydaniu ani symboli źródłowych.

## Dane zweryfikowane

| Właściwość | V2.2 | V2.4 |
|---|---:|---:|
| Rozmiar | 135 072 B | 135 096 B |
| SHA-256 | `58B3C467373D8EE2E5C060F35125AF179A422D127CEA0F2C95C7463BC99508C4` | `4BEFDF6B58E063F03901F190000D790E60D20D0A23E5EEB2B6F6840F1830E98E` |
| Wbudowany identyfikator | `DMT-99 V2.2` | `DMT-99 V2.4` |

- V2.4 jest większa o 24 bajty.
- Tylko 21,59% bajtów jest identycznych na tym samym przesunięciu. Tak niski wynik wynika głównie z przesuniętych adresów względnych, a nie z przepisania 78% programu.
- W publicznej mapie 439 funkcji V2.4 odnaleziono 152 funkcje o unikalnej, identycznej zawartości w V2.2; obejmują 16 998 bajtów kodu.
- Oba obrazy są aplikacjami RISC-V dla rodziny WCH CH32V303. Pliki zaczynają się od aplikacji pod adresem łączenia `0x00006400`; nie zawierają wcześniejszego bootloadera.
- Grafiki językowe nie znajdują się w tych plikach BIN. Są przechowywane w osobnej pamięci SPI W25Q64.

## Zmiany o najwyższej pewności

1. **Ekran bieżącego pomiaru i formatowanie jednostek**  
   Zmieniono duży blok funkcji rozpoczynający się w V2.4 pod `0x00009CAA`. Analiza wywołań wiąże go z dekodowaniem cyfr pomiarowych, doborem jednostek, formatowaniem tekstu oraz widokami pomiar/rejestracja/monitor. W tym miejscu V2.4 usuwa około 12 bajtów kodu względem V2.2.

2. **Historia pomiarów**  
   Zmieniono funkcję V2.4 pod `0x00014578`, odpowiedzialną za rysowanie wierszy historii oraz formatowanie wartości i jednostek. Blok jest większy o około 26 bajtów.

3. **Dane i układ obrazu**  
   Po uwzględnieniu dwóch zmian kodu pozostaje około 10 bajtów różnicy netto w późniejszej części obrazu. Jest to zgodne z korektą danych/układu, ale nie pozwala nazwać konkretnej funkcji użytkowej.

4. **Numer wersji**  
   Zmieniono tekst identyfikacyjny z `V2.2` na `V2.4`.

## Czego analiza nie potwierdza

- Nie ma podstaw, aby przypisać V2.4 konkretną „naprawę dokładności”, „poprawę kalibracji” albo nowy tryb pomiarowy.
- Zmiany adresów w setkach funkcji są w dużej części skutkiem przesunięcia kodu po lokalnych modyfikacjach.
- Emulacja cyfrowa nie sprawdza toru analogowego, zabezpieczeń wejścia, dokładności ADC ani kalibracji miernika.

## Emulacja

V2.4 uruchomiono jako oryginalny kod maszynowy w modelu CH32V303 z emulacją SRAM, przerwań, UART, SPI/W25Q64, systemu plików, dekodera JPEG i wyświetlacza ST7789.

- błąd wykonania: brak;
- zatrzymanie CPU: nie;
- wejście do głównej pętli: tak;
- polecenia panelu: 22 556;
- narysowane piksele: 269 553;
- ramka UART: `AA550514000000000019`;
- SHA-256 bufora ekranu: `04543EC39A33F881520F0EB444D80EAF41CEE609CB56E24DA1B2673785D72864`.

To potwierdza, że V2.4 można emulować funkcjonalnie po stronie cyfrowej. Nie jest to test fizycznego miernika.

## Podstawa analizy

- dostarczone obrazy V2.2 i V2.4;
- statyczna analiza instrukcji RV32IMAC i dopasowanie funkcji;
- publiczna rekonstrukcja i emulator DMT-99: <https://github.com/smhgzll/dmt-99-multimeter-custom-firmware>;
- oficjalna strona plików FNIRSI: <https://www.fnirsi.com/pages/manuals-firmwares>.


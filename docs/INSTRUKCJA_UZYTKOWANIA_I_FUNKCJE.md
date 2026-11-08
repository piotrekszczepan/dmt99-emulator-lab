# DMT-99 V2.4 — funkcje i ograniczenia wersji PL/English

## Bezpieczeństwo

- Czarny przewód podłącz do `COM`.
- Czerwony przewód podłącz do `VΩ` dla napięcia, rezystancji, ciągłości, diody, pojemności, częstotliwości i temperatury.
- Gniazd `mA` i `10A` używaj wyłącznie do pomiaru prądu szeregowo.
- Nigdy nie przykładaj napięcia, gdy przewód pozostaje w gnieździe prądowym.
- Rezystancję, diodę, ciągłość i pojemność mierz w obwodzie odłączonym od zasilania.
- NCV i LIVE są pomocnicze i nie potwierdzają braku napięcia.

## Funkcje

Automatyczne rozpoznawanie, napięcie DC/AC, prąd DC/AC w A i mA/µA, rezystancja, ciągłość, dioda, pojemność, częstotliwość, temperatura °C/°F, NCV, LIVE, HOLD, REL, rejestracja trendu, progi i historia do 30 rekordów.

Wersja naprawcza zachowuje fabryczne symbole, Polski jako język domyślny oraz English jako drugi język. Motyw 1 jest wymuszony. Motywu 2 nie da się bezpiecznie spolszczyć samym plikiem aplikacji, ponieważ jego JPEG-y znajdują się w W25Q64.

## Wycofana wersja

Firmware z pełnymi nazwami pomiarów i SHA-256 `38F5160F60F718B9F2120FCF03655BB07F590D01526A5B2720E146A8527C44F1` powodował zakłócenia rysowania na fizycznym ekranie. Nie należy go używać. Emulator nie wykrył tej usterki, co potwierdza, że test cyfrowy nie zastępuje próby sprzętowej.

Prawdziwy oscyloskop nadal nie jest wiarygodnym rozszerzeniem: rozpoznany protokół dostarcza wynik pomiaru, nie potwierdzony szybki strumień surowych próbek ADC. Realne dodatki programowe to wolny trend, MIN/MAX/AVG oraz eksport CSV w emulatorze.

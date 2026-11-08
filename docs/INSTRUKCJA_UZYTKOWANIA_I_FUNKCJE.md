# FNIRSI DMT-99 V2.4 — instrukcja użytkowania i funkcje

Pełna instrukcja wersji eksperymentalnej PL znajduje się w pakiecie użytkownika. Poniżej opis funkcji miernika i ograniczeń projektu źródłowego.

## Bezpieczeństwo

- Czarny przewód: `COM`. Czerwony: `VΩ` dla napięcia, rezystancji, ciągłości, diody, pojemności, częstotliwości i temperatury.
- Gniazd `mA` i `10A` używaj wyłącznie do prądu mierzonego szeregowo.
- Nigdy nie mierz napięcia z czerwonym przewodem w gnieździe prądowym.
- Rezystancję, ciągłość, diodę i pojemność mierz w obwodzie odłączonym od zasilania; kondensator rozładuj.
- NCV i LIVE są pomocnicze i nie potwierdzają braku napięcia.

## Funkcje

Automatyczne rozpoznawanie, napięcie DC/AC, rezystancja, ciągłość, test diody, pojemność, częstotliwość, prąd DC/AC w A i mA/µA, temperatura °C/°F, NCV, LIVE, HOLD, REL, rejestracja trendu, monitorowanie progów i historia do 30 rekordów.

W przygotowanym patchu ekran regularny używa nazw ASCII: `Pojemnosc`, `Rezystancja`, `Napiecie DC`, `Napiecie AC`, `Ciaglosc`, `Czestotliwosc`, `Prad DC A`, `Prad DC mA`, `Temperatura`, `Prad AC A`, `Prad AC mA`.

## Polskie znaki i oscyloskop

Fabryczny renderer obsługuje drukowalne ASCII 32–126. UTF-8 lub „rozszerzone ASCII” nie doda bezpiecznie polskich liter. Pełne glify wymagają własnego renderera lub zmian grafik W25Q64, których zwykły updater USB nie zapisuje.

Prawdziwy oscyloskop nie jest obecnie wiarygodnym rozszerzeniem: rozpoznany protokół dostarcza ramki wyniku podobne do segmentów LCD, nie potwierdzony szybki strumień ADC. Realne rozszerzenia to wolny trend, MIN/MAX/AVG i eksport CSV w emulatorze. Pomiar mocy wymagałby jednoczesnego napięcia i prądu, czego nie potwierdzono.

## Granice

Emulator wykonuje kod RV32 i modele urządzeń cyfrowych. Nie sprawdza fizycznej dokładności, kalibracji, izolacji ani zabezpieczeń wejść. Repozytorium nie zawiera firmowego BIN ani zrzutu W25Q64.

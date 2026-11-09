# Audyt tlumaczenia V8

## Zakres spolszczenia aplikacji

V8 tlumaczy wyswietlane przez aplikacje elementy polskiego slotu jezykowego, zachowujac English jako drugi jezyk. Dla Motywu 2 polskie napisy sa rysowane kodem aplikacji zamiast niemieckich JPEG-ow z W25Q64.

- menu: Wybor trybu, Ustawienia progow, Historia, Ustawienia systemu, Resetuj, O mierniku;
- tryby: Pomiar, Rejestracja, Monitor;
- progi: Napiecie, Prad, Temperatura;
- historia: Tryb, Pomiar;
- system: Motyw, Jezyk, Polski, English;
- reset: UWAGA, Przywrocic wszystkie ustawienia?, Resetuj, Powrot;
- informacje: FNIRSI DMT-99, Miernik cyfrowy, Firmware V2.4 PL, Motyw 2: polski;
- komunikat ladowania: polski.

V8 obsluguje poczatkowe rysowanie i dodatkowe odswiezenia wywolywane dla zapisanych widokow 1, 2 i 3. Testy utworzyly trzy rozne obrazy z zaznaczeniem odpowiednio `Pomiar`, `Rejestracja` i `Monitor`.

## Elementy pozostawione jako symbole

Symbole pomiarowe i jednostki, np. `V~`, `V`, `A`, `mA`, `Hz`, `Ohm`, `C/F`, pozostaja w oryginalnej postaci. Wariant z pelnymi nazwami byl wczesniej wycofany po wystapieniu zaklocen grafiki na fizycznym urzadzeniu.

## Granica bootloadera

Plik aktualizacji aplikacji jest ladowany od adresu MCU `0x6400`. Nie zawiera pierwszych `0x6400` bajtow (`0x0000-0x63FF`), gdzie znajduje sie rezydentny bootloader USB. To bootloader wyswietla chinsko-angielska instrukcje kopiowania firmware na dysk `BOOT` i nacisniecia `AUTO`.

Wniosek: tego ekranu nie da sie spolszczyc przez bezpieczna modyfikacje dostarczonego pliku aplikacji. Potrzebny bylby zweryfikowany zrzut bootloadera, znajomosc jego kontroli integralnosci i sprawdzona metoda odzyskania urzadzenia po nieudanym zapisie. V8 celowo nie dotyka bootloadera.

## Dowody

- `PL_THEME2_TEXT_MANIFEST_V8.json` - adresy przechwyconych wywolan i suma pliku;
- `PL_THEME2_VALIDATION.json` - pelny raport testow z wynikiem `pass: true`;
- `emulacja-v8-motyw2-wybor-trybu1.png`;
- `emulacja-v8-motyw2-wybor-trybu2.png`;
- `emulacja-v8-motyw2-wybor-trybu3.png`.

Emulator sprawdza wykonanie kodu i piksele, ale nie dowodzi bezpieczenstwa elektrycznego ani zachowania fizycznego bootloadera. Koncowe potwierdzenie musi byc wykonane na mierniku bez podlaczonego niebezpiecznego napiecia.

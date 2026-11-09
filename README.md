# Endless Waves Alerts

Dagelijkse controle van de surfvoorspelling voor Wijk aan Zee, Vendée (Bud Bud), Crozon (Lostmarc'h), Cap Ferret, Biarritz-omgeving, Peniche en Taghazout. Een pushmelding komt alleen als een regio boven **zijn eigen drempel** uitkomt. Alles is te zien in een web-app op je iPhone.

## Hoe het werkt

```
GitHub Action (dagelijks 07:40 UTC = 08:40 NL-wintertijd)
  1. scripts/fetch.py    golf- en windvoorspelling van Open-Meteo, ECMWF en GFS apart,
                         16 dagen, inclusief zonsopkomst en -ondergang
  2. scripts/analyze.py  toetst aan de spotcriteria, zoekt reeksen, past de drempels
                         per regio toe en onthoudt wat al gemeld is
  3. commit              data/ (voorspelling + archief), out/ (meldingen, verslag),
                         docs/data.json (web-app), state/
  4. ntfy                pushmelding naar je iPhone bij nieuw / zekerder / vervallen

Web-app (GitHub Pages, map docs/)   startscherm: per regio per dag golfhoogte + gekleurde
                                    conditiegraad (slecht/matig/redelijk/goed/top);
                                    tik op een regio of dag voor details en plankadvies

```

## Definitie van een goede dag

**Reisbestemmingen** (gelijk aan Endless Waves): minstens 2 ochtenduren (07–11, binnen daglicht) waarin:

- de golfrichting binnen de swellbogen van de spot valt;
- de piekperiode minstens 10 s is (Bud Bud: 11 s);
- de golfhoogte (Hs) binnen het bereik van de spot ligt;
- de wind offshore is (marge +22,5°, maximaal 22 kn) of zwak (≤ 6 kn);
- de windstoten hooguit 28 kn zijn.

**Wijk aan Zee** (thuisspot): de hele dag met daglicht telt. Verder:

- periode minstens 6 s;
- Hs 0,8–2,5 m;
- swell uit NNW tot W;
- wind uit O tot ZO, of hooguit 8 kn.

Dit is een eerste schatting; stel bij na ervaring.

**Strenge variant (★):** periode minstens 12 s (Wijk aan Zee 8 s), 3 goede uren, en geen windstilte-regel: alleen echte offshore wind telt.

**Krachtig:** Hs minstens 1,5 m en periode minstens 12 s (Wijk aan Zee 1,3 m en 8 s).

## Conditiegraad in de app

| Graad | Betekenis |
|---|---|
| top | goede dag én krachtig of streng goed |
| goed | voldoet aan de definitie hierboven |
| redelijk | één voorwaarde net niet, of maar 1 goed uur |
| matig | twee voorwaarden niet |
| slecht | drie of meer niet |

Golfhoogte = Hs (diep water) van de beste spot, gemiddeld over beide modellen. De graad is het gemiddelde van de modellen, naar beneden afgerond. Een open balk betekent onzeker: de modellen verschillen 2 of meer graden, of de dag telt op deze termijn niet mee.

## Zekerheid en termijn

| Begint over | Label | Regel |
|---|---|---|
| ≤ 3 dagen | bevestigd | één model goed is genoeg |
| 4–7 dagen | waarschijnlijk | één model goed is genoeg |
| 8+ dagen | kans | **beide modellen** moeten het eens zijn; heeft er maar één nog data, dan moet die dag ook volgens de strenge variant goed zijn |

## Drempels per regio (`config/spots.json`, blok `alert`)

| Regio | Melden bij |
|---|---|
| Wijk aan Zee | 1 goede sessie, maximaal 3 dagen vooruit |
| Vendée, Crozon | 2 goede dagen op rij |
| Cap Ferret | 3 dagen op rij, waarvan minstens 1 streng |
| Biarritz-omgeving | 3 dagen op rij, waarvan minstens 1 streng of krachtig |
| Peniche | 3 dagen op rij, waarvan op minstens 2 dagen beide modellen het eens zijn |
| Taghazout | 4 dagen op rij, minstens 2 krachtige dagen, op minstens 2 dagen beide modellen eens |

Je kunt dit altijd aanpassen: wijzig de getallen in `config/spots.json` op GitHub (potloodje → Commit). De volgende run gebruikt ze. Reeksen onder de drempel staan wel in de app, gemarkeerd als "onder drempel", maar geven geen melding.

## Spotcriteria

| Regio | Spots | Bron |
|---|---|---|
| Wijk aan Zee | Wijk aan Zee | eigen eerste schatting |
| Vendée | Bud Bud, La Sauzaie | Bud Bud: eigen regels; La Sauzaie: surf-forecast |
| Crozon | Lostmarc'h, La Palue | surf-forecast |
| Cap Ferret | Le Truc Vert, Le Grand Crohot | surf-forecast |
| Biarritz-omgeving | La Gravière, Lafitenia | richting surf-forecast, hoogte Surfline |
| Peniche | Supertubos, Lagide | Supertubos: Surfline; Lagide: richting surf-forecast |
| Taghazout | Anchor Point, Boilers | Anchor: Surfline; Boilers: richting surf-forecast |

Aanbevolen: neem de richtingen eenmalig over uit de Surfline spot guides zodra Chrome met Surfline aan staat.

## Installatie (eenmalig, ±20 minuten)

1. **Repository.** Maak op GitHub een openbare repository `endless-waves-alerts`. Upload alle bestanden uit deze map, met de mappen (`.github/workflows` erbij).
2. **Actions.** Ga naar het tabblad Actions, schakel workflows in, kies **Endless Waves forecast → Run workflow**. In de log moet `ok, 0 problemen` staan. Bij problemen: zie de modelnamen bovenaan `scripts/fetch.py`.
3. **Web-app.**
   - Ga naar Settings → Pages en kies "Deploy from a branch": `main`, map `/docs`.
   - Na een minuut staat de app op `https://<gebruiker>.github.io/endless-waves-alerts/`.
   - Open die in Safari en kies Deel → **Zet op beginscherm**.
4. **Pushmeldingen.**
   - Installeer de gratis app **ntfy** (App Store) en abonneer je op een zelfbedacht, lastig te raden onderwerp, bijvoorbeeld `ew-derek-7k2p9x`.
   - Ga op GitHub naar Settings → Secrets and variables → Actions:
     - Secret `NTFY_TOPIC` = dat onderwerp.
     - Variable `APP_URL` = de Pages-URL.
   - Een tik op de melding opent dan de web-app.

## Getij en beste tijd

- **Getij:** zeespiegel per spot (`sea_level_height_msl`, model van Météo-France via Open-Meteo). Dit loopt ongeveer 9 dagen vooruit. Hoog- en laagwater zijn op het hele uur afgerond (±30 min).
- **Getijvoorkeur per spot** staat in `config/spots.json` (`tide`: low, low-mid, mid, mid-high, high, all). Behalve "all" bij Killer Point en Banana Point (surf-forecast) en "half, liefst opkomend" bij Bud Bud (eigen regels) zijn dit aannames om bij te stellen.
- **Beste tijd:** het blok van 1–3 daglichturen waarin swellrichting, periode, golfhoogte en wind kloppen. Een blok met het juiste getij, zwakke offshore wind en langere periode gaat voor.
- **Golfhoogte-maximum per spot:** beachbreaks 2,1 m (hoger is vaak te groot). Riffen en points mogen hoger: La Sauzaie 2,5 · La Gravière 2,5 · Lafitenia 2,8 · Supertubos en Lagide 2,3 · Banana Point 2,5 · Boilers 3,0 · Anchor Point en Killer Point 3,5.

## Bekende beperkingen

- **Golfmodel op afstand.** Het golfmodel kijkt naar een punt 30–50 km uit de kust, net als Endless Waves. Lokale effecten (zandbanken, refractie, pieren) zitten er niet in. Check Surfline voordat je boekt.
- **Geen getij.** Belangrijk voor Bud Bud, Lostmarc'h en Wijk aan Zee.
- **ECMWF-golven** reiken op Open-Meteo mogelijk minder ver dan 16 dagen. Daarna telt alleen GFS, met de strenge eis.
- **Wijk aan Zee** is met windswell lastig te voorspellen; de criteria zijn een eerste schatting.
- **Controle na 4–6 weken.** Met het archief in `data/archive/` meten we hoe vaak meldingen uitkwamen, en vergelijken we met de Surfline-meldingen.

# Endless Waves – proces en keuzes

Centraal logboek van alle keuzes, zodat een volgend gesprek hier verder kan. Bijgewerkt: 9 november 2026.

## 1. Waar staat wat

| Wat | Waar |
|---|---|
| Repository (code, instellingen, data) | github.com/derekboerma-dev/endless-waves-alerts (openbaar) |
| iPhone-app (GitHub Pages) | https://derekboerma-dev.github.io/endless-waves-alerts/ (op beginscherm gezet) |
| Onderzoek "Endless Waves" (ranglijst 45 regio's) | Claude-doc "Endless Waves", tab Data-ranglijst |
| Methode van het onderzoek | Projectdocument `claude/Endless Waves methode.md` |
| Werking van het meldsysteem | `README.md` in de repository (ook als projectdocument) |
| Dit logboek | `PROCES.md` in de repository (ook als projectdocument) |
| Spotcriteria en drempels | `config/spots.json` |
| Quiver voor de app | `docs/quiver.json` |

## 2. Hoe het begon

1. **Gezinsvakantie juli–augustus.** Bali/Bingin-achtig, minder verwesterd, villa bij goede surf, iets voor de kinderen (5 en 7), koffie en yoga voor Dereks partner. Onderzocht: Lombok, Sumbawa, Sri Lanka, Siargao, Midden-Amerika, Mexico, Brazilië, Marokko, Portugal en meer.
2. **Werken op afstand, enkele weken, zonder gezin.** De criteria werden, in volgorde: golfconsistentie, golfkwaliteit, reisafstand, budget.
3. **Kritiek van Derek.** Taghazout was te hoog ingeschat, en de bronnen waren niet vergelijkbaar. Daarop is de **Endless Waves-methode** opgezet.

## 3. Endless Waves-methode (onderzoek)

- **Data:** ERA5-heranalyse (Open-Meteo), 2020–2024, elk uur. Golfpunt minstens 0,35° uit de kust in de richting van de swell.
- **Spotcriteria:** uit de Surfline spot guides. Waar die ontbreken: surf-forecast.com, met een zekerheidslabel (A: alleen Surfline, B: gemengd, C: alleen surf-forecast).
- **Goede dag:** minstens 2 ochtenduren (07–11) waarin alles klopt:
  - swellrichting binnen de bogen van de spot;
  - Tp ≥ 10 s;
  - Hs binnen het bereik van de spot;
  - offshore wind (±22,5° marge) of ≤ 6 kn.
- **Strenge variant:** Tp ≥ 12 s, 3 uur, geen windstilte-regel. Index = gemiddelde van basis en streng over de beste 3 maanden.
- **Getoetst** op Anchor Point en Coxos (seizoenen kloppen met Surfline). Vijf fouten gevonden en hersteld:
  - ontbrekende ERA5-data eind 2024;
  - golfpunt aan de lijzijde van eilanden;
  - verkeerd gelezen hoogteteksten;
  - big-wave-spots in de selectie;
  - aanvulling via surf-forecast nodig.
- **Uitkomst:**
  - Top wereldwijd: Lombok, Bali, Peru Lobitos, Mentawai, Oaxaca, Chicama.
  - Europa: Peniche (69% goede dagen jan–mrt) is beter dan Hossegor en Sagres (±60%), Taghazout (55%) en Ericeira (51%).
  - Taghazout is dus niet consistenter dan de Portugese westkust, wat past bij Dereks ervaring.
- **Bekende zwakte:** passaatwind-eilanden worden onderschat (Barbados, Malediven, Mauritius en andere).

## 4. Meldsysteem (Endless Waves Alerts)

### Waarom deze opzet
- Claudes cloudomgeving mag Open-Meteo niet bereiken, GitHub wel. Daarom haalt een **GitHub Action** de data op en bewaart die in de repository. Chrome, de computer en een inlog zijn niet nodig.
- Surfline-meldingen vergeleken: per spot en per moment, geen reeksen, geen vergelijking tussen bestemmingen en geen mate van zekerheid. **Keuze:** eigen systeem voor het vroege signaal en het vergelijken; Surfline (12 dagen) blijft de controle vóór het boeken.
- Bestaande GitHub-projecten bekeken (surfs-up, surf-check, Surf_Alert_Northsea, mcp-surf-forecast). Niets dekte de behoefte. Ideeën overgenomen: ntfy-push, daglicht en windstoten, strengere eisen bij langere termijn.

### Werking
1. **`scripts/fetch.py`** (dagelijks 07:40 UTC en na elke push op config/scripts) haalt van Open-Meteo, voor 16 dagen:
   - golven, apart voor ECMWF (`ecmwf_wam025`, ±15 dagen) en GFS (`ncep_gfswave025`, 16 dagen);
   - wind (`ecmwf_ifs025`, `gfs_seamless`), met windstoten, zonsopkomst en zonsondergang;
   - getij per spot (`sea_level_height_msl`, ±9 dagen).
2. **`scripts/analyze.py`** doet het volgende:
   - toetst per spot en per dag (Endless Waves-definitie, alleen daglicht);
   - geeft een conditiegraad 0–4;
   - zoekt reeksen per regio en past de drempels per regio toe;
   - onthoudt wat al gemeld is in `state/alerted.json`;
   - schrijft `docs/data.json` voor de app, `out/alerts.json`, `out/report.html` en `out/ntfy.txt`.
3. **Push via ntfy** bij een nieuwe reeks, een reeks die zekerder wordt of een melding die vervalt. *Staat nog on hold* (zie §7).
4. **Archief:** elke dag `data/archive/<datum>.json.gz`, om later te meten hoe vaak meldingen uitkwamen.

### Zekerheid
- **Bevestigd:** begint over ≤ 3 dagen.
- **Waarschijnlijk:** begint over 4–7 dagen.
- **Kans:** begint over 8 dagen of later. Vanaf dag 8 telt een dag alleen als beide modellen het eens zijn. Heeft er maar één model data, dan moet die dag ook volgens de strenge variant goed zijn.

### Drempels per regio
Lager voor dichtbij en goedkoop, hoger voor ver en duur (keuze van Derek).

| Regio | Melden bij |
|---|---|
| Wijk aan Zee (thuisspot) | 1 goede sessie, maximaal 3 dagen vooruit, hele daglichtperiode |
| Vendée (Bud Bud), Crozon (Lostmarc'h) | ≥ 2 dagen op rij |
| Cap Ferret | ≥ 3 dagen, waarvan ≥ 1 streng |
| Zuidwest-Frankrijk (Hossegor–Guéthary) | ≥ 3 dagen, waarvan ≥ 1 streng of krachtig |
| Peniche | ≥ 3 dagen, waarvan op ≥ 2 dagen beide modellen eens |
| Taghazout | ≥ 4 dagen, ≥ 2 krachtig, op ≥ 2 dagen beide modellen eens |

### Spots en criteria

| Groep | Spot | Hs (m) | Getij | Bron richting |
|---|---|---|---|---|
| Nederland | Wijk aan Zee | 0,8–2,0 | half | eigen schatting (Tp ≥ 6 s) |
| Frankrijk | Bud Bud | 1,0–2,1 | half, liefst opkomend | eigen regels (Bud Bud-skill) |
| Frankrijk | La Sauzaie | 1,0–2,5 | half | surf-forecast |
| Frankrijk | Lostmarc'h, La Palue | 1,0–2,1 | half | surf-forecast |
| Frankrijk | Le Grand Crohot, Le Truc Vert | 1,0–2,1 | half | surf-forecast |
| Frankrijk | La Gravière | 1,0–2,5 | half | surf-forecast (hoogte Surfline) |
| Frankrijk | Les Cavaliers, Grande Plage | 1,0–2,1 | half | surf-forecast |
| Frankrijk | Lafitenia | 1,0–2,8 | half | surf-forecast (hoogte Surfline) |
| Portugal | Supertubos | 1,3–2,3 | laag–half | Surfline |
| Portugal | Lagide | 0,8–2,3 | half | surf-forecast (hoogte Surfline) |
| Taghazout | Anchor Point | 1,3–3,5 | alle | Surfline |
| Taghazout | Killer Point | 1,3–3,5 | alle | surf-forecast |
| Taghazout | Boilers | 1,3–3,0 | alle | surf-forecast (hoogte Surfline) |
| Taghazout | Banana Point | 0,8–2,5 | alle | surf-forecast (hoogte Surfline) |

- Hs-maximum 2,1 m voor beachbreaks is een keuze van Derek: hoger is vaak te groot. Riffen en points mogen hoger.
- Getijvoorkeuren zijn aannames, behalve Bud Bud (eigen regels) en Killer Point en Banana Point (surf-forecast).

### Conditiegraad (app)
- **Top:** goede dag én krachtig (Hs ≥ 1,5 m en Tp ≥ 12 s) of streng goed.
- **Goed:** voldoet aan de definitie.
- **Redelijk:** één voorwaarde net niet, of 1 goed uur.
- **Matig:** twee voorwaarden niet.
- **Slecht:** drie of meer niet (grijs, "niets te surfen").

### Beste tijd per dag
Het blok van 1–3 daglichturen waarin swellrichting, periode, golfhoogte en wind kloppen. Een blok met het juiste getij, zwakke offshore wind en langere periode gaat voor. Getijtijden zijn afgerond op het hele uur (±30 min).

### Plankadvies (Dereks quiver)

| Plank | Wanneer |
|---|---|
| Onfire 6'0 (35 L) | < 1,0 m (NL < 1,2 m) of Tp < 8 s |
| Channel Islands Happy Everyday 5'11 | 1,0–1,8 m |
| Morris 6'4 pintail | 1,8–2,5 m (Tp < 13 s) |
| Bitch Boards 6'4 HP | 1,8–2,5 m bij Tp ≥ 13 s |
| Lost Mayhem 7'2 | ≥ 2,5 m |

## 5. App (iPhone, web-app op GitHub Pages)

Keuzes van Derek, in volgorde:
1. **Weinig tekst** op het startscherm.
2. **In de stijl van Surfline:**
   - per spot een rij en per dag een kolom;
   - de golfhoogte staat boven een gekleurde balk;
   - een open balk betekent onzeker;
   - een gemarkeerde dag hoort bij een melding.
3. **Details pas na het aantikken.** Per aangeraden dag:
   - beste tijd;
   - golf, periode en wind;
   - getij met hoog- en laagwatertijden;
   - plankadvies;
   - de modellen uitklapbaar.
4. **Per surfspot**, gegroepeerd: Nederland, Frankrijk, Portugal, Taghazout.
5. **Slecht is grijs.**
6. **Kopbalk:** vast bovenaan, grote titel (32 px).
7. **Opstartscherm** van 4 seconden (zon met bewegende golven).
8. **Menubalk onderin:** Voorspelling en Quiver. De quiver toont per board de maten, tail, vinnen, herkomst en wanneer je hem pakt, met een getekend silhouet. Foto's van internet zijn bewust niet gebruikt (auteursrecht); eigen foto's kunnen in `docs/img/`.

Eerder afgewezen of vervangen: een kalender zonder hoogtes; een rode kleur voor slecht; één kaart per regio (te algemeen); een native iOS-app (vereist een Mac/Xcode en €99 per jaar).

## 6. Installatiestatus (9 november 2026)

- [x] Repository aangemaakt en Claude GitHub App geïnstalleerd (Claude kan pushen).
- [x] Workflow draait (eerste run: 0 problemen; ECMWF ±15 dagen, GFS 16 dagen, getij ±9 dagen).
- [x] GitHub Pages aan; app op het beginscherm.
- [x] Workflow "Test pushmelding" toegevoegd.
- [ ] **ntfy-push: on hold** op verzoek van Derek. Te doen: ntfy-app plus abonnement, secret `NTFY_TOPIC`, variabele `APP_URL`, daarna "Test pushmelding" draaien. Het voorgestelde onderwerp staat niet in deze openbare repository; zie het projectdocument.
- [ ] Optioneel: geplande Claude-taak voor een uitgebreid HTML-verslag (`TAAKOPDRACHT.md`).

## 7. Open punten

1. ntfy-push aanzetten (on hold).
2. Spotrichtingen eenmalig overzetten naar de Surfline spot guides zodra Chrome met Surfline beschikbaar is. Dan is alles één bron.
3. Getijvoorkeuren en de criteria voor Wijk aan Zee toetsen aan Dereks ervaring.
4. Na 4–6 weken het archief gebruiken om te meten hoe vaak meldingen uitkwamen, en vergelijken met de Surfline-meldingen.
5. Layout verder bijschaven met echte data.
6. Eventueel Nederland en Denemarken uitbreiden (idee uit Surf_Alert_Northsea).

## 8. Werkwijze met Claude

- **Wijzigen kan via chat.** Claude past de repository aan en pusht. Een push op `config/` of `scripts/` start direct een nieuwe run; app-wijzigingen staan na ±1 minuut live.
- **Getest wordt** met nepdata en schermafbeeldingen op iPhone-formaat, in licht en donker.
- **Antwoorden** kort en in het Nederlands.

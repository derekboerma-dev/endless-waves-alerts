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
| Peniche, Sagres | ≥ 3 dagen, waarvan op ≥ 2 dagen beide modellen eens |
| Taghazout | ≥ 4 dagen, ≥ 2 krachtig, op ≥ 2 dagen beide modellen eens |

### Spots en criteria

| Groep | Spot | Hs (m) | Getij | Bron richting |
|---|---|---|---|---|
| Nederland | Wijk aan Zee | 0,8–2,0 | half | eigen schatting (Tp ≥ 6 s) |
| Frankrijk | Bud Bud | 1,0–2,1 | half, liefst opkomend | eigen regels (Bud Bud-skill) |
| Frankrijk | La Sauzaie | 1,0–2,5 | half | surf-forecast |
| Frankrijk | Lostmarc'h, La Palue | 1,0–2,1 | half | surf-forecast |
| Frankrijk | Cap Ferret, Le Truc Vert | 1,0–2,1 | half | surf-forecast |
| Frankrijk | La Gravière | 1,0–2,5 | half | surf-forecast (hoogte Surfline) |
| Frankrijk | Les Cavaliers | 1,0–2,1 | half | surf-forecast |
| Frankrijk | Lafitenia | 1,0–2,8 | half | surf-forecast (hoogte Surfline) |
| Portugal | Supertubos | 1,3–2,3 | laag–half | Surfline |
| Portugal | Lagide | 0,8–2,3 | half | surf-forecast (hoogte Surfline) |
| Portugal (Sagres) | Tonel | 0,8–2,3 | alle | surf-forecast (hoogte Surfline) |
| Portugal (Sagres) | Beliche | 1,2–3,5 (beschut: heeft meer swell op zee nodig) | half | surf-forecast |
| Taghazout | Anchor Point | 1,3–3,5 | alle | Surfline |
| Taghazout | Killer Point | 1,3–3,5 | alle | surf-forecast |
| Taghazout | Boilers | 1,3–3,0 | alle | surf-forecast (hoogte Surfline) |

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
| Morris 6'4 Waterskate (round tail, breed) | 1,0–2,2 m zachte, vollere golven (Tp < 10 s); niet bij hol (correctie van Derek: de Morris is een round tail, geen pintail) |
| Channel Islands Happy Everyday 5'11 | 1,0–1,8 m, schoon, langere periode |
| Bitch Boards 6'4 HP | ≥ 1,8 m, steil/hol of krachtige groundswell, ook grote dagen (geen echte step-up in de quiver) |
| Lost 7'2 (shaper Matt "Mayhem" Biolos) | < 0,8 m en korte periode: glijden op slappe dagen. Uitgezocht: met 20½ × 2⅝ (± 42 L) een mid-length, geen step-up en geen longboard |

### Wetsuitadvies (watertemperatuur overdag, Open-Meteo `sea_surface_temperature`)
| Water | Wetsuit |
|---|---|
| ≥ 24 °C | boardshort of lycra |
| 21–24 °C | shorty of 2 mm |
| 18–21 °C | 3/2 |
| 15–18 °C | 4/3 |
| 12–15 °C | 5/4 + booties |
| < 12 °C | 5/4 of 6/5 + booties, handschoenen en cap |

Bij luchttemperatuur onder 8 °C één stap dikker.

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
7. **Opstartscherm** (zon met bewegende golven), zie punt 8.
8. **Opstartscherm 3 s** (was 4 s). Titelbalk toont "Data bijgewerkt <dag datum, tijd>" (moment van ophalen, niet van uploaden).
9. **Spotdetail toont ook:** watertemperatuur, luchttemperatuur, wetsuitadvies, zonsopkomst/-ondergang.
10. **Menubalk onderin:** Voorspelling en Quiver. De quiver toont per board de maten, tail, vinnen, herkomst en wanneer je hem pakt, met een getekend silhouet. Foto's van internet zijn bewust niet gebruikt (auteursrecht); eigen foto's kunnen in `docs/img/`.

11. **Favorieten:** ster rechtsboven op een spotpagina; favorieten staan bovenaan het startscherm. Bewaard op het toestel zelf.
12. **Open in Surfline:** directe link bij Anchor Point en Bud Bud (Surfline-ID bekend); bij de andere spots de Surfline-kaart op de coördinaten van de spot. Directe links kunnen er komen zodra de Surfline-ID's bekend zijn (via Chrome).
13. **Sessie beoordelen:** na een sessie geef je dezelfde graad als de app (niets/matig/redelijk/goed/top), met de plank en een opmerking. De app opent een ingevuld GitHub-issue ("Sessie: <spot> <datum>"); jij tikt op "Submit new issue". De volgende run zet het in `docs/sessions.json`, samen met wat de app die dag voorspelde, en sluit het issue. Onder "Jouw sessies" op de spotpagina zie je ze terug. Doel: later drempels, getijvoorkeuren en plankadvies per spot bijstellen op echte ervaring in plaats van aannames. Let op: de repository is openbaar, dus ook deze issues.

14. **Startscherm = variant A "Tegels"** (gekozen uit vijf ontwerpen op het canvas "Endless Waves – startscherm varianten"): per spot een rij gekleurde tegels met de golfhoogte erin; open tegel = onzeker; omlijnd = hoort bij een melding.
15. **Bovenaan de spotpagina = variant B "Spotkaart met golfgrafiek"**: per dag een staafje (hoogte = golfhoogte, kleur = conditie) met de beste dag rechtsboven; tik op een staafje om naar die dag te springen.

16. **Spotkeuze 9 nov (Derek):** Banana Point, Grande Plage en Le Grand Crohot verwijderd; Tonel en Beliche (Sagres) en Cap Ferret toegevoegd. De Quiver-tab houdt de titel "Endless Waves".
17. **Persoonlijk maximum 2,1 m (Derek, 9 nov; sinds punt 18 over de hoogte op de spot):** `defaults.max_hs_personal` = 2,1 m. Dit kapt het hoogtebereik van elke spot af, behalve bij thuisspots (Wijk aan Zee). Het bereik per spot blijft in de config staan: zet je het maximum hoger of haal je het weg, dan geldt weer het spotbereik.
18. **Golfhoogte op de spot (Derek, 9 nov, optie 1).** Alle hoogtegrenzen gaan nu over de geschatte hoogte op de spot, zoals Surfline die toont, en niet meer over open zee (30–50 km uit de kust).
    - **Schatting** (`surf_height` in analyze.py):
      - brekerhoogte volgens Komar & Gaughan, met hoogte én periode;
      - minder hoogte als de swell schuin binnenkomt;
      - beschuttingsfactor `exposure` per spot: Bud Bud 0,9 · Lafitenia 0,85 · Lagide 0,8 · Tonel 0,9 · Beliche 0,6 · Anchor 0,7 · Killer 0,8 · Boilers 0,9;
      - algemene schaal `surf_scale` 0,85.
    - **Weergave:** een bereik van ±15 %.
    - **Omrekening:** de oude bereiken zijn omgerekend bij 11 s (Wijk aan Zee 7 s) met swell recht op de spot. Ze staan bewaard als `hs_open_zee_oud`.
    - **Wat over open zee blijft gaan:** "krachtig" (Hs ≥ 1,5 m en Tp ≥ 12 s).
    - **Plankadvies:** de grenzen zijn aangepast aan de spothoogte.
    - **App:** tegels en grafiek tonen de spothoogte. De dagkaart toont het bereik plus de hoogte op open zee.
    - **Sessiescore:** nieuw veld "Hoe hoog was het?". De kalibratie geeft vanaf 3 sessies per spot een hint om `exposure` bij te stellen.
    - **Te doen:** Derek vergelijkt thuis via Chrome een aantal dagen met Surfline. Daarna `surf_scale` en `exposure` per spot bijstellen.
19. **Persoonlijk maximum van 2,1 m geschrapt (Derek, 9 nov).** Het maximum per spot komt nu uit spotgidsen, als "holds up to" in hoogte op de spot. Bron per spot in `hs_max_bron`:
    - **2,5 m:** Bud Bud, Cap Ferret, Le Truc Vert, La Gravière (wannasurf).
    - **3,0 m:**
      - La Sauzaie, Lostmarc'h, La Palue, Supertubos, Lagide, Tonel (wannasurf);
      - Les Cavaliers (yeeew, zwakke bron);
      - Beliche (geen maximum gevonden, gelijk aan Tonel).
    - **3,5 m:**
      - Anchor Point (surfmaroc / mondo.surf);
      - Killer Point (surfholidays: tot dubbel overhead);
      - Boilers (mondo.surf: experts tot 12 ft+).
    - **4,0 m:** Lafitenia (wannasurf).
    - **Ondergrenzen:** ongewijzigd.
20. **Surfline-vergelijking en spotgidsen (9 nov, via Chrome met Dereks account).**
    - **Vergelijking:** de LOTUS-dagwaarden over 16 dagen naast de app gelegd. De app schatte gemiddeld 1,6 keer te hoog (mediaan Surfline/app 0,62).
      - `surf_scale` gaat van 0,85 naar 0,52.
      - `exposure` per spot is bijgesteld naar de verhouding van die spot. Opvallend: Bud Bud 0,55 en Boilers 0,37 (Surfline geeft Boilers veel minder dan Anchor).
      - Lostmarc'h staat niet op Surfline en krijgt de factor van La Palue.
      - Na de bijstelling liggen de dagen 0–7 binnen ±0,3 m van Surfline.
    - **Surfline-ID's:** voor alle spots behalve Lostmarc'h opgeslagen. De Surfline-knop opent nu de juiste pagina.
    - **Spotgidsen** (alleen beschikbaar voor Wijk aan Zee, de spots in het Baskenland/Landes, Portugal en Marokko):
      - een eigen Nederlandse samenvatting plus swell, wind, getij, hoogte, seizoen, niveau, bodem en gevaren in `guide`, met een blok "Spotgids" in de app;
      - hoogtebereik = de "ideal size" uit de gids, met een vertaaltabel: heup ≈ 0,9 m · schouder 1,2 · hoofd 1,5 · overhead 2,1 · dubbel overhead 3,0 (+ = 3,7) · 3x overhead 4,5;
      - swell- en windbogen overgenomen uit de gids (punt 1 van de open punten is daarmee afgerond voor deze spots).
    - **Franse spots zonder Surfline-gids** (Bud Bud, La Sauzaie, Lostmarc'h, La Palue, Cap Ferret, Truc Vert): ondergrens meegeschaald (minimaal 0,6 m), bovengrens van wannasurf.

Eerder afgewezen of vervangen: Surfline-achtige rijen met balkjes (vervangen door tegels); varianten C (beste kansen eerst), D (per dag) en E (bollen); een kalender zonder hoogtes; een rode kleur voor slecht; één kaart per regio (te algemeen); een native iOS-app (vereist een Mac/Xcode en €99 per jaar).

## 5b. Leren van sessies

- Het beoordelingsscherm vraagt ook het **tijdstip**: ochtend (07–11), middag (11–16), avond (16–20) of een begintijd.
- **`scripts/calibrate.py`** draait elke run. Per sessie:
  - pakt het de voorspelling van die dag uit het archief (dag 0);
  - rekent de graad opnieuw uit met dezelfde regels als de app;
  - haalt golf, periode, richting, wind en getij op het sessietijdstip op.
- Per spot berekent het het gemiddelde verschil (jouw graad min de voorspelde graad) en geeft het hints, pas vanaf 3 sessies. Bijvoorbeeld:
  - de criteria zijn te streng of te ruim;
  - je scoort beter bij opkomend of afgaand tij;
  - je hebt goede sessies buiten het hoogtebereik gehad;
  - de gemiddelde score per plank.
- **Uitvoer:** `docs/calibration.json` (in de app onder "Jouw sessies") en `out/kalibratie.md` (leesbaar, voor de evaluatie met Claude).
- **Afspraak:** elke paar weken samen bijstellen ("kijk naar mijn sessies"). Claude stelt wijzigingen voor, Derek keurt goed, en ze worden hier vastgelegd. Automatisch bijsturen pas vanaf ±10–15 sessies per spot.
- **Idee voor later:** voorspellingen toetsen aan metingen (golfboeien) en aan het eigen archief (voorspelling van dag N tegenover dag 0) om afwijkingen per spot en per termijn te meten en te corrigeren.

## 6. Installatiestatus (9 november 2026)

- [x] Repository aangemaakt en Claude GitHub App geïnstalleerd (Claude kan pushen).
- [x] Workflow draait (eerste run: 0 problemen; ECMWF ±15 dagen, GFS 16 dagen, getij ±9 dagen).
- [x] GitHub Pages aan; app op het beginscherm.
- [x] Workflow "Test pushmelding" toegevoegd.
- [ ] **ntfy-push: on hold** op verzoek van Derek. Te doen: ntfy-app plus abonnement, secret `NTFY_TOPIC`, variabele `APP_URL`, daarna "Test pushmelding" draaien. Het voorgestelde onderwerp staat niet in deze openbare repository; zie het projectdocument.

- Geschrapt (9 nov, keuze Derek): de geplande Claude-taak met een HTML-verslag. De app en de ntfy-push dekken dit, en zo kost het dagelijkse systeem geen tokens. `TAAKOPDRACHT.md` is verwijderd.

## 7. Open punten

1. ntfy-push aanzetten (on hold).
2. Getijvoorkeuren en de criteria voor Wijk aan Zee toetsen aan Dereks ervaring.
3. Layout verder bijschaven met echte data.
4. Eventueel Nederland en Denemarken uitbreiden (idee uit Surf_Alert_Northsea).
5. Overwogen maar niet gebouwd: reistijd en globale kosten per groep in de app.
6. Afgerond op 9 nov: spotrichtingen naar de Surfline-gidsen (waar die bestaan) en Surfline-ID's voor alle spots behalve Lostmarc'h.

### 7a. Verbeterplan voorspelling (afgesproken 10 nov)

| # | Stap | Status | Wat |
|---|---|---|---|
| 1 | Swell en windzee apart | **gebouwd 10 nov**, daarna exposure opnieuw gefit (verschil met Surfline dag 1–6: 0,1–0,3 m) | Hoogte op de spot per component (swell, tweede swell, windzee) en samen via energie. Periode en richting van de grootste component. Mist een model de windzee, dan wordt de rest-energie als korte windzee gerekend. |
| 2 | Fijnmazige wind eerste 48 uur | **gebouwd 10 nov** | Per land het eerste model met data: NL KNMI HARMONIE · FR Météo-France AROME HD · PT/MA ICON-EU (DMI HARMONIE Europe gaf geen data). Vervangt ECMWF- en GFS-wind voor de eerste 48 uur (`hires_wind_hours`). |
| 3 | Golfpunt per spot | **gebouwd 10 nov** | Golfdata van de dichtstbijzijnde zeecel bij elke spot, met het regiopunt als reserve. |
| 4 | Vaker vergelijken met Surfline | open | Als Chrome met Surfline openstaat: Surfline-dagwaarden opslaan (`data/surfline/<datum>.json`) en per spot een factor fitten die afhangt van periode en richting, niet één vaste factor. Na 3–4 keer stabiel. Werkwijze: zie punt 20 in de beslissingen (iframes op surfline.com, regel "LOTUS Model" gevolgd door 16 dagwaarden). |
| 5 | Sessiescores als meting | doorlopend | Derek vult na elke sessie graad en "hoe hoog was het" in. Vanaf 3 sessies per spot geeft de kalibratie hints; vanaf ±10 automatisch bijstellen. |
| 6 | Trefzekerheid meten | open, vanaf ±1 dec | Uit `data/archive/` meten hoe vaak meldingen op dag 1–3, 4–7 en 8+ uitkwamen; daarna de drempels per termijn bijstellen. |

## 8. Werkwijze met Claude

- **Wijzigen kan via chat.** Claude past de repository aan en pusht. Een push op `config/` of `scripts/` start direct een nieuwe run; app-wijzigingen staan na ±1 minuut live.
- **Getest wordt** met nepdata en schermafbeeldingen op iPhone-formaat, in licht en donker.
- **Antwoorden** kort en in het Nederlands.

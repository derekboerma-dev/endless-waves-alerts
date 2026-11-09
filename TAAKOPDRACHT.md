# Opdracht voor de geplande Claude-taak (Endless Waves Alerts)

> Deze tekst is de opdracht die elke run krijgt. Elke run is een nieuwe sessie zonder geheugen van eerdere chats; alles wat nodig is staat hier of in de repository.

Je controleert de surfvoorspelling voor Derek. Antwoord in het Nederlands, kort.

1. Haal de repository op: `git clone --depth 1 https://github.com/<GITHUB-GEBRUIKER>/endless-waves-alerts.git`
2. Lees `out/alerts.json`.
   - Als `generated` niet de datum van vandaag is: de GitHub Action is niet gelopen. Stuur één kort bericht ("Voorspellingsdata van vandaag ontbreekt; controleer het tabblad Actions op GitHub") en stop.
   - Als `problems` niet leeg is: noem het in één regel onderaan het verslag.
   - Als `notify` false is: stop zonder bericht of bestand. Er is niets nieuws.
3. Als `notify` true is, maak een HTML-verslag. De pushmelding via ntfy is dan al verstuurd; jouw verslag is de uitgebreide versie (één bestand, Nederlands, licht/donker, mobielvriendelijk). Gebruik `out/report.html` als inhoudelijke basis en voeg toe:
   - Bovenaan per melding (nieuw, zekerder geworden, vervallen): regio, data, aantal dagen, zekerheid (kans / waarschijnlijk / bevestigd), hoeveel dagen beide modellen het eens zijn, strenge dagen, krachtige dagen, spots.
   - Per goede dag de golf (Hs, periode, richting) en wind uit `all_runs` en de tabel.
   - Wijk aan Zee is een thuisspot: daar gaat het om één goede sessie (tijdvak staat in `window`), niet om een reeks.
   - Plankadvies per dag staat al in `docs/data.json` (veld `board`). Gebruik die, of pas dezelfde regels toe:
     - 0,6–1,0 m of zwak: Onfire 6'0 35L.
     - 1,0–1,8 m schoon: Channel Islands Happy Everyday 5'11.
     - 1,0–2,2 m zachte, vollere golven (periode < 10 s): Morris 6'4 Waterskate (breed, round tail; nooit bij hol).
     - 1,8–2,5 m steil/hol of krachtige groundswell: Bitch Boards 6'4 HP.
     - Grote dagen (2,5 m+): ook Bitch Boards 6'4 HP (er is geen echte step-up).
     - < 0,8 m, slap: Lost 7'2 (mid-length, ± 42 L).
   - Advies: "kans" = in de gaten houden; "waarschijnlijk" = vluchten en verblijf checken; "bevestigd" = boeken als het past. Raad aan om op Surfline (12 dagen) mee te kijken.
   - Een korte uitleg van de definitie (gelijk aan Endless Waves) en de bron: Open-Meteo, modellen ECMWF en GFS.
   - Een link naar de web-app (de GitHub Pages-URL van de repository).
4. Stuur het HTML-bestand met SendUserFile en geef in 2–3 zinnen de kern: welke regio, welke data, hoe zeker.
5. Verander niets in de repository.

# Grünwelle – Projektstand für neue Chats

Kurzfassung, damit ein neuer Chat ohne den alten Verlauf weiterarbeiten kann.
Zuerst diese Datei lesen, dann gezielt in `index.html` suchen (grep), nicht die ganze Datei laden.

## Was es ist
Web-App (iPhone, Safari / Home-Bildschirm) als Mischung aus TrafficPilot (Ampelprognose, Tempo für die grüne Welle)
und Waze (Navigation, Meldungen der Nutzer). Teststadt Leipzig. Für viele Nutzer gedacht, gelernte Daten werden geteilt.

- Live: https://dms314.github.io/Gruenwelle/ (GitHub Pages, Branch `main`, Wurzelordner)
- Repo: DMS314/Gruenwelle
- Nutzer: kein Mac, keine native App/CarPlay vorerst. Spricht Deutsch, testet auf dem iPhone im Auto.

## Dateien
| Datei | Inhalt |
|---|---|
| `index.html` | Die ganze App (HTML, CSS, JS in einer Datei, ca. 140 KB). `APP_VERSION` oben im Skript bei jeder Änderung hochzählen (Format `TT.MM.JJJJ · n`), die App lädt neue Versionen selbst nach. |
| `signals.json`, `cameras.json`, `roadworks.json` | Täglich von `.github/workflows/ampeln.yml` gebaut (Geofabrik Sachsen → osmium, Autobahn-API) |
| `mobile.json` | Amtlich angekündigte mobile Kontrollen (Tag + Straße → OSM-Linien), 2× täglich von `mobile.yml` (`tools/build_mobile.py`). Quelle bisher nur Stadt Bonn Open Data (CC0). |
| `trams/stops.json`, `trams/d/<n>.json` | Straßenbahn-Fahrplan Leipzig, Mo+Do von `trams.yml` aus gtfs.de (DELFI, CC BY 4.0) |
| `tools/*.py` | Build-Skripte für obige Daten |
| `manifest.webmanifest`, `icon-*.png` | Home-Bildschirm-App (display fullscreen, Farbe #1d2935) |

## Technik in `index.html`
- Karte: MapLibre GL 5.24 (unpkg), OpenFreeMap „liberty“, 3D-Gebäude, Symbole als SVG über `map.addImage`.
- Ampel-Lernen: Halt/Losfahren/Durchfahrt je Ampel und Richtungssektor → Umlauf C (40–140 s) und Grünzeit per Kreisanpassung (`fit`), Zeitfenster nach Tageszeit. Tempo-Empfehlung nie über dem Limit.
- Navigation: Suche Photon (Nähe zuerst: bbox ±30 km + Rest „Weiter entfernt“), Route OSRM über FOSSGIS, Neuberechnung, Ton- oder Sprachansagen (Ton Standard wegen iOS-Radio-Bug).
- Spurassistent: OSRM `intersections[].lanes`; Fahrstreifenzahl entlang der Route über Overpass (`fetchLaneProfile`); keine Empfehlung vor einer Engstelle oder über eine Ampelkreuzung mit unbekannten Spuren hinweg (`laneDrop`, `crossBefore`), rechts bevorzugt wenn danach eine Spur endet. Spurfenster gleitet bei Empfehlung über die Abbiegeanzeige (`laneMove`).
- Darstellung: Pfeil und Kamera pro Bild geglättet (`smoothFrame`, `SM`), auf der Route entlang; `map.redraw()` im selben Bild gegen Zittern. Abbiegeanzeige füllt sich auf den letzten 500 m (`--np`).
- Tempolimit: OSM `maxspeed` (auch `:forward/:backward`, `:conditional` mit einfachen Zeitfenstern, `zone:maxspeed` wie `DE:30`/`DE:urban`) über Overpass im Umkreis 900 m, Mittelpunkt 250 m voraus (`loadVL`, neu ab 450 m Abstand). Abgleich mit Position + Richtung bzw. Route (`matchVL`, bleibt am bisherigen Weg). Schild neben dem Tacho, Tacho rot ab Limit + 4 km/h. `effLim()` ersetzt `set.limit` für Empfehlung und Skala (Rad: nie über Einstellung), Blitzer nutzt es als Ersatz. Schalter `set.vlim`.
- Mobile Blitzer: Meldungstyp `mob` (3 h, Bestätigung verlängert), nur bei Blitzer-Schalter sichtbar/meldbar (`visRep`, `renderTypes`). `mobCams()` speist dieselbe Warnbox wie feste Blitzer (`camAhead`/`checkCams`, Ton nur bei zu schnell). Nach dem Vorbeifahren 20 s „Mobiler Blitzer noch da?“ (`mobAsk`) statt der normalen Meldungswarnung.
- Angekündigte Kontrollen: `loadAnn`/`annAt`/`showAnn`, heutige Straßen rot gestrichelt (Layer `ann`), Warnbox „Kontrolle angekündigt“, wenn man längs auf der Straße fährt (≤ 18 m); feste/mobile Punkte haben Vorrang. Quellenrecherche 11/2026: Leipzig gibt Pläne nur an Medien (LVZ, MDR, BILD, Leipzig Fernsehen), PD Chemnitz „Blitztipps“ eingestellt, Stadt Chemnitz veröffentlicht nicht online, Blitzer.de/verkehrslage.de nicht frei. Weitere Kandidaten: Polizei-Wochenlisten auf presseportal.de (Fließtext, z. B. Südosthessen, Saarland).
- Verkehrsmeldungen (Verkehrswarndienst wie im Radio): live direkt im Browser von `verkehr.autobahn.de/o/autobahn/<A>/services/warning` (CORS offen), A4, A9, A13, A14, A17, A38, A72, A143, alle 3 Min beim Fahren (`loadVwd`). Karte: Layer `vwd`/`vwd-line`, Antippen → `showVwd` (Baustellen-Blatt). Hinweis bis 3 km voraus im Meldungsfenster ohne Knöpfe (`.alert.info`, `vwdAhead`, auf Route per `snap`, sonst gleichgerichtete Linie). Schalter `set.vwd`. Radio-Blitzer selbst: keine offene Quelle (Sender ohne Schnittstelle, Leipzig-Pläne nur an Medien). Polizei-Seite vwdmeldungen.asp ohne Inhalt/maschinenlesbare Form; Sachsen-Verkehrsmeldungen in der Mobilithek erst geplant, dort bisher nur Baustellen.
- Seitenmenü: Während der Navigation (`.app-nav`) wird `.top` (Vollbild, Wohin?, Einstellungen) zum Menü links mit Lasche `#drawerTab` (Buchstaben „Menü“ aufrecht untereinander, 29×72 px, offen blau); öffnen per Lasche oder Wischen vom linken Rand, schließt nach Auswahl, beim Antippen der Karte oder Wischen nach links. Außerhalb der Navigation unverändert oben. Darin „Ansagen“: Lautlos / Wichtige / Alle (`set.vol`, `renderVol`, `WICHTIG` = near, blitz, wx, vwd, test); Lasche zeigt bei Lautlos/Wichtige ein kleines Symbol. Ansage-Art (Töne/Sprache) bleibt in den Einstellungen.
- Ton: iOS hält AudioContext nach Hintergrund an → `audioWake()` bei Rückkehr (visibilitychange) und jeder Berührung während der Fahrt; `say()` wartet nach `cancel()` 120 ms (iOS verschluckt sonst). Diagnosezeile „Ton“ (`audioState`). Bei „Signaltöne“ gilt `audioSession.type='ambient'` → Stummschalter am iPhone schaltet Töne stumm.
- Stimme: `pickVoice()` wählt die beste deutsche Gerätestimme (Premium > Erweitert > Standard > Effektstimmen wie Grandma/Eddy), Auswahl + „Probe“ in den Einstellungen (`set.voice`, `renderVoices`), Tempo 1,0 bei guten Stimmen. Achtung: WebKit (alle iOS-Browser, auch Home-Bildschirm-App) gibt nachgeladene Stimmen (Premium/Erweitert, z. B. Petra) und Siri-Stimmen nicht an Webseiten weiter (WebKit-Bug 290497), nur fest eingebaute. Bessere Stimme nur per Cloud-Sprachdienst oder native App. Cloud-Stimmen (z. B. neuronale TTS) bräuchten bezahlten Dienst + Schlüssel → nicht umgesetzt.
- Simulation: eigene Uhr `SIM.t` (1 Runde = 1 s Simulationszeit, Runden alle 1000/`SIM.mul` ms); Fahrt (`step=v·dt`) und Rotphasen (`until` in Simulationssekunden) skalieren gemeinsam mit 2×/4×. Vorher fuhr 2× real 4× und 4× real 16×, Rot lief in Echtzeit.
- Navi-Karte: Kopf + Spurleiste in einem Block `#nav .main` (gemeinsamer Hintergrund und Fortschrittsbalken), Spuren bündig unter dem Text, klappen per max-height weich auf (`laneMove`, `setNavh`). Zusatz „für … in …“ nur, wenn die Spurempfehlung zu einer späteren Abbiegung gehört als oben angezeigt.
- Weitere Funktionen: Blitzer (aus, wie Waze), Baustellen, Straßenbahn-Abfahrten + Hinweis „Bahn fährt ab, Ampel kann umschalten“, DWD-Wetterwarnungen (Bright Sky `/alerts`, dezent als rundes Symbol je Warnart mit Warndreieck in Stufenfarbe: `wxKind`, `WXI`, `WXCOL`), gespeicherte Orte (`gw_fav`, Karte antippen / Fahrzeug antippen / „Wohin?“), Meldungen löschen, Simulation (`SIM`, lernt und teilt nichts), Querformat nur Navi + Ampel, Vollbild-Hinweis.
- Speicher auf dem Gerät: `gw_set, gw_obs, gw_reps, gw_sig, gw_sigc, gw_log, gw_recent, gw_pend, gw_fav, gw_hide, gw_wxseen`.

## Supabase (gemeinsame Daten)
Projekt `mevgfarshklqbszhtabr` (Frankfurt). Tabellen `obs`, `reports` (Typen pol, unf, stau, gef, bau, mob; Check-Constraint + Prüfung in `add_report`) mit RLS ohne Policies, Zugriff nur über SECURITY-DEFINER-Funktionen für `anon`:
`add_obs(items)`, `get_obs(sigs)`, `add_report(p_type,p_lat,p_lon,p_token)`, `vote_report(p_id,p_still)`,
`delete_report(p_id,p_token)` (eigene Meldung per Schlüssel-Hash), `get_reports(p_lat,p_lon,p_km)`.
Publishable Key steht in `index.html` (`SB`). Supabase-Hinweis „anon kann SECURITY DEFINER aufrufen“ ist Absicht.

## Arbeitsweise
1. In `index.html` per Python-Ersetzung ändern (exakte Textstellen, jeweils Anzahl prüfen), `APP_VERSION` hochzählen.
2. Test mit Playwright und nachgestellten Daten (Testhaken: Host `gw.test` → `window.__gw`). Echte Server sind aus der Sandbox oft nicht erreichbar.
3. Commit mit Co-Authored-By-Zeilen, `git -c push.negotiate=true push origin main`. Pages ist nach ca. 1 Minute aktuell.
4. Antworten an den Nutzer: kurz, deutsch, was sich ändert und wie man es sieht.

## Offen / zurückgestellt
- Rechtliches vor Veröffentlichung: Impressum, Datenschutzerklärung, Teilen als Opt-in beim ersten Start, Schrift und MapLibre selbst hosten, Markenprüfung „Grünwelle“. Vom Nutzer erstmal zurückgestellt.
- Ampeldaten der Stadt Leipzig: Die Stadt liefert Schaltzeitprognosen von rund 400 Ampeln an TrafficPilot (GEVAS), Pilot ab 28.10.2025, stadtweit seit April 2026. Projekt ABSOLUT II (Data Week Leipzig 2026) nennt Datenbus mit LSA-Daten/Schaltzeitprognosen. Zuständig: Mobilitäts- und Tiefbauamt, Verkehrs- und Datenmanagement, Thomas Grzeschik (Sachgebietsleiter), mta-verkehrsmanagement@leipzig.de, 0341 123-9084. Anfrage nach Datenzugang für Grünwelle entworfen (11/2026), Antwort offen.
- Ideen: Autobahn-Sperrungen (`services/closure`), Stau bei der Routenwahl berücksichtigen, Ton bei Tempoüberschreitung, Park+Ride-Belegung, Unfallatlas, Ratenbegrenzung in Supabase, Anfrage an die Stadt Leipzig nach Ampeldaten.
- Bestätigt: unterer Rand im Hochformat, kein Zittern mehr (ab 25.11.2026 · 8).
- Behoben in 25.11.2026 · 11: Meldungsbox („… noch da?“) lag im Hochformat hinter dem Bedienfeld, jetzt darüber (`--panh`).
- Unbestätigt: Tempolimit-Anzeige im Auto (ab 25.11.2026 · 10), mobile Blitzer (ab · 11), angekündigte Kontrollen (ab · 12, erst in Bonn sinnvoll testbar), Autobahn-Verkehrsmeldungen (ab · 13), Spurassistent an der Permoser Kreuzung (Theodor-Heuss-Straße, danach einspurig).

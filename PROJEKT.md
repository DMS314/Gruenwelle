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
| `trams/stops.json`, `trams/d/<n>.json` | Straßenbahn-Fahrplan Leipzig, Mo+Do von `trams.yml` aus gtfs.de (DELFI, CC BY 4.0) |
| `tools/*.py` | Build-Skripte für obige Daten |
| `manifest.webmanifest`, `icon-*.png` | Home-Bildschirm-App (display fullscreen, Farbe #1d2935) |

## Technik in `index.html`
- Karte: MapLibre GL 5.24 (unpkg), OpenFreeMap „liberty“, 3D-Gebäude, Symbole als SVG über `map.addImage`.
- Ampel-Lernen: Halt/Losfahren/Durchfahrt je Ampel und Richtungssektor → Umlauf C (40–140 s) und Grünzeit per Kreisanpassung (`fit`), Zeitfenster nach Tageszeit. Tempo-Empfehlung nie über dem Limit.
- Navigation: Suche Photon (Nähe zuerst: bbox ±30 km + Rest „Weiter entfernt“), Route OSRM über FOSSGIS, Neuberechnung, Ton- oder Sprachansagen (Ton Standard wegen iOS-Radio-Bug).
- Spurassistent: OSRM `intersections[].lanes`; Fahrstreifenzahl entlang der Route über Overpass (`fetchLaneProfile`); keine Empfehlung vor einer Engstelle oder über eine Ampelkreuzung mit unbekannten Spuren hinweg (`laneDrop`, `crossBefore`), rechts bevorzugt wenn danach eine Spur endet. Spurfenster gleitet bei Empfehlung über die Abbiegeanzeige (`laneMove`).
- Darstellung: Pfeil und Kamera pro Bild geglättet (`smoothFrame`, `SM`), auf der Route entlang; `map.redraw()` im selben Bild gegen Zittern. Abbiegeanzeige füllt sich auf den letzten 500 m (`--np`).
- Weitere Funktionen: Blitzer (aus, wie Waze), Baustellen, Straßenbahn-Abfahrten + Hinweis „Bahn fährt ab, Ampel kann umschalten“, DWD-Wetterwarnungen (Bright Sky `/alerts`), gespeicherte Orte (`gw_fav`, Karte antippen / Fahrzeug antippen / „Wohin?“), Meldungen löschen, Simulation (`SIM`, lernt und teilt nichts), Querformat nur Navi + Ampel, Vollbild-Hinweis.
- Speicher auf dem Gerät: `gw_set, gw_obs, gw_reps, gw_sig, gw_sigc, gw_log, gw_recent, gw_pend, gw_fav, gw_hide, gw_wxseen`.

## Supabase (gemeinsame Daten)
Projekt `mevgfarshklqbszhtabr` (Frankfurt). Tabellen `obs`, `reports` mit RLS ohne Policies, Zugriff nur über SECURITY-DEFINER-Funktionen für `anon`:
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
- Ideen: Autobahn-Sperrungen, echte Tempolimits (OSRM maxspeed), Park+Ride-Belegung, Unfallatlas, Ratenbegrenzung in Supabase, Anfrage an die Stadt Leipzig nach Ampeldaten.
- Unbestätigt: unterer Rand auf dem iPhone im Hochformat (Home-Bildschirm-App ggf. neu hinzufügen), Zittern des Pfeils nach Version 25.11.2026 · 8, Spurassistent an der Permoser Kreuzung (Theodor-Heuss-Straße, danach einspurig).

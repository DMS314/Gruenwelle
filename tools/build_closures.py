"""Baut closures.json: Verkehrsraumeinschränkungen der Stadt Leipzig (Verkehrs- und Tiefbauamt, opendata.leipzig.de, WFS).
Nur heute gültige Einträge, die den Autoverkehr betreffen. Vollsperrungen: blocked=True (die App umfährt sie bei jeder Route).
Aufruf: build_closures.py <ziel.json>"""
import json, sys, re, datetime, urllib.request, urllib.parse, math

SRC = None  # zum Testen: GRUENWELLE_WFS=<datei.json> statt Abruf bei der Stadt
URL = ('https://geodienste.leipzig.de/l3/OpenData/wfs?VERSION=1.3.0&REQUEST=getFeature'
       '&typeName=OpenData%3Averkehrsraumeinschraenkungen&outputFormat=application/json&srsName=EPSG:4326')
UA = 'Gruenwelle/1.0 (+https://github.com/DMS314/Gruenwelle)'
dst = sys.argv[1]
today = datetime.date.today().isoformat()

def thin(ring, maxn=40):
    if len(ring) <= maxn:
        return [[round(x, 6), round(y, 6)] for x, y in ring]
    step = len(ring) / (maxn - 1)
    out = [ring[int(i * step)] for i in range(maxn - 1)] + [ring[-1]]
    return [[round(x, 6), round(y, 6)] for x, y in out]

def de(d):
    try:
        return datetime.date.fromisoformat(d[:10]).strftime('%d.%m.%Y')
    except Exception:
        return ''

import os
if os.environ.get('GRUENWELLE_WFS'):
    data = json.load(open(os.environ['GRUENWELLE_WFS'], encoding='utf-8'))
else:
    req = urllib.request.Request(URL, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)

FOOT = re.compile(r'Gehweg|Fu(ß|ss)weg|Fu(ß|ss)g(ä|ae)nger|Radweg|Radverkehr|Gehbahn', re.I)
CAR = re.compile(r'Fahrbahn|Fahrstreifen|Fahrspur|halbseitig|Einbahn|Ampel|LSA|Abbiege|Umleitung|gesperrt|Sperrung', re.I)
items, n_block, stat = [], 0, {}
for f in data.get('features', []):
    p = f.get('properties') or {}
    g = f.get('geometry') or {}
    b, e = (p.get('beginn') or '')[:10], (p.get('ende') or '')[:10]
    if (b and b > today) or (e and e < today):
        continue
    art = (p.get('sperrart') or '').strip()
    msg = (p.get('meldung') or '').strip()
    if msg.lower() == 'keine meldung':
        msg = ''
    if art in ('Sperrung Fußgängerverkehr', 'Sperrung Radverkehr'):
        continue
    full = art == 'Vollsperrung' or (re.search(r'Vollsperr|voll ?gesperrt', msg, re.I) and not FOOT.search(msg))
    # Nur was die Fahrbahn betrifft: Vollsperrung, halbseitige Sperrung oder eine Meldung, die Fahrbahn/Fahrstreifen/Ampel nennt.
    # „Einschränkungen“ ohne Meldung sind meist Arbeiten am Gehweg oder Seitenstreifen (z. B. Telekommunikation an der Paunsdorfer Straße) → weglassen.
    road = msg and CAR.search(msg) and not FOOT.search(msg)
    stat[art or '(leer)', 'mit Meldung' if msg else 'ohne Meldung', 'Fahrbahn' if (full or art == 'halbseitige Sperrung' or road) else 'weg'] = \
        stat.get((art or '(leer)', 'mit Meldung' if msg else 'ohne Meldung', 'Fahrbahn' if (full or art == 'halbseitige Sperrung' or road) else 'weg'), 0) + 1
    if not full and art != 'halbseitige Sperrung' and not road:
        continue
    polys = g.get('coordinates') or []
    if g.get('type') == 'Polygon':
        polys = [polys]
    rings = [pl[0] for pl in polys if pl and pl[0] and len(pl[0]) >= 4]
    if not rings:
        continue
    ring = max(rings, key=len)
    lon = sum(c[0] for c in ring) / len(ring)
    lat = sum(c[1] for c in ring) / len(ring)
    addr = re.sub(r'\s+', ' ', (p.get('adresse') or '').strip()) or 'Straße'
    kind = 'Vollsperrung' if full else (art or 'Einschränkung')
    sub = kind + (f' · bis {de(e)}' if e else '')
    desc = [x for x in [msg, (p.get('sparte') or '').strip() and 'Anlass: ' + p['sparte'].strip(),
                        b and f'Seit {de(b)}'] if x]
    items.append({'id': 'lz-' + str(p.get('objectid')), 'src': 'leipzig', 'title': ('Sperrung: ' if full else 'Baustelle: ') + addr,
                  'sub': sub, 'desc': desc, 'lon': round(lon, 6), 'lat': round(lat, 6),
                  'line': thin(ring), 'poly': thin(ring), 'blocked': bool(full), 'end': e, '_msg': msg})
    n_block += bool(full)

# ---- Lage prüfen: „Knoten X/Y“ muss an der Kreuzung von X und Y liegen (Datensatz der Stadt hat teils versetzte Flächen,
# z. B. Stöhrerstraße/Brahestraße 540 m daneben). Kreuzung aus OpenStreetMap (gemeinsamer Knoten beider Straßen).
OVERPASS = ['https://maps.mail.ru/osm/tools/overpass/api/interpreter', 'https://overpass.private.coffee/api/interpreter',
            'https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']

def street_names(addr):
    parts = [re.sub(r'\s+\d.*$', '', re.sub(r'\(.*?\)', '', x)).strip(' ,.') for x in re.split(r'\s*/\s*|\s+Ecke\s+', addr)]
    return [x for x in parts if len(x) > 3]

def mdist(a, b):  # a, b = (lon, lat)
    return math.hypot((a[0] - b[0]) * 69600, (a[1] - b[1]) * 111000)

def ring(lon, lat, r=25, n=10):
    return [[round(lon + r / 69600 * math.cos(2 * math.pi * i / n), 6), round(lat + r / 111000 * math.sin(2 * math.pi * i / n), 6)] for i in range(n)] + \
           [[round(lon + r / 69600, 6), round(lat, 6)]]

knots = [(it, street_names(it['title'].split(': ', 1)[1])) for it in items]
knots = [(it, nm) for it, nm in knots if len(nm) >= 2]
fixed = 0
if knots:
    names = sorted({n for _, nm in knots for n in nm[:2]})
    rx = '|'.join(re.sub(r'([.$*+?(){}|])', r'[\1]', n) for n in names if not re.search(r'[\\\[\]^"]', n))  # Sonderzeichen als [x], ohne Backslash (Overpass-Zeichenkette)
    q = f'[out:json][timeout:120];way["highway"]["name"~"^({rx})$"](51.20,12.15,51.48,12.62);out body geom;'
    ways = None
    for url in OVERPASS:
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({'data': q}).encode(), headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=150) as r:
                ways = json.load(r).get('elements', [])
            break
        except Exception as e:
            print('Overpass', url, e)
    if ways is not None:
        print(f'{len(ways)} Straßenabschnitte aus OpenStreetMap für {len(names)} Namen')
        nodes = {}  # name -> {node_id: (lon, lat)}
        for w in ways:
            nm = w.get('tags', {}).get('name')
            for nid, g in zip(w.get('nodes', []), w.get('geometry', [])):
                nodes.setdefault(nm, {})[nid] = (g['lon'], g['lat'])
        for it, nm in knots:
            a, b = nodes.get(nm[0], {}), nodes.get(nm[1], {})
            shared = [a[k] for k in a.keys() & b.keys()]
            if not shared:
                continue
            c = (it['lon'], it['lat'])
            k = min(shared, key=lambda x: mdist(x, c))
            dpoly = min(mdist(k, tuple(p)) for p in it['poly'])
            if dpoly > 60:
                print(f"Lage korrigiert: {it['title']} – Fläche der Stadt lag {dpoly:.0f} m neben der Kreuzung")
                it['poly'] = it['line'] = ring(*k)
                it['lon'], it['lat'] = round(k[0], 6), round(k[1], 6)
                it['desc'].append(f'Lage auf die Kreuzung laut OpenStreetMap gesetzt (Fläche der Stadt lag {dpoly:.0f} m daneben)')
                it['fix'] = round(dpoly)
                fixed += 1
    if ways is None:
        # Kartendienst nicht erreichbar: Korrekturen aus dem letzten Lauf übernehmen, damit sie nicht verloren gehen
        try:
            old = {i['id']: i for i in json.load(open(dst, encoding='utf-8')).get('items', []) if i.get('fix')}
        except Exception:
            old = {}
        for it, nm in knots:
            o = old.get(it['id'])
            if o:
                for k in ('poly', 'line', 'lat', 'lon', 'fix'):
                    it[k] = o[k]
                it['desc'].append(f"Lage auf die Kreuzung laut OpenStreetMap gesetzt (Fläche der Stadt lag {o['fix']} m daneben)")
                fixed += 1
        print(f'Kartendienst nicht erreichbar, {fixed} Korrekturen aus dem letzten Lauf übernommen')
    print(f'{len(knots)} Kreuzungs-Sperrungen geprüft, {fixed} Lage korrigiert')


# ---- Einseitige Sperrungen (nur eine Fahrtrichtung oder ein Abbiegen gesperrt). Die Stadt führt sie meist als „Einschränkungen“
# mit einer kleinen Fläche irgendwo an der Stelle, z. B. „Zuckelhäuser Straße 5: … Sperrung der Ausfahrt Sommerfelder Straße auf die
# Zuckelhäuser Straße stadteinwärts“ (Fläche mitten auf der Kreuzung, die Umleitung führt über dieselbe Kreuzung!).
# Aus dem Text wird die gesperrte Fahrtrichtung bestimmt: dirs = [{d: Richtung in Grad (gesperrte Fahrtrichtung), p: Punkte, t: Text}].
# Die App sperrt eine Route nur, wenn sie dort in dieser Richtung (±60°) fährt, und umfährt nur dann.
CENTER = (12.3747, 51.3405)   # Markt Leipzig (für stadteinwärts/stadtauswärts)
NM = r"[A-ZÄÖÜ][\wäöüß.\-]*(?:\s+(?:[A-ZÄÖÜ][\wäöüß.\-]*|am|an|der|zur|zum|im))*?\s*(?:[Ss]tra(?:ß|ss)e|[Ss]tr\.|[Ww]eg|[Pp]latz|[Aa]llee|[Rr]ing|[Gg]asse|[Dd]amm|[Uu]fer|[Mm]arkt|[Bb]rücke)"
PLACE = r"[A-ZÄÖÜ][\wäöüß\-]+(?:\s+[A-ZÄÖÜ][\wäöüß\-]+)?"

def norm(n):
    return re.sub(r'\s+', ' ', re.sub(r'([Ss])tr\.$', r'\1traße', n.strip(' ,.'))).strip()

def brg(a, b):  # a, b = (lon, lat) → Grad
    return (math.degrees(math.atan2((b[0] - a[0]) * 69600, (b[1] - a[1]) * 111000)) + 360) % 360

def addr_street(it):
    a = it['title'].split(': ', 1)[1]
    a = re.split(r'\s*/\s*|\s+Ecke\s+|\s+zu\s+|\s+zw\.\s+|\s+zwischen\s+|\s+-\s+|,', a)[0]
    return norm(re.sub(r'\s+\d.*$', '', re.sub(r'\(.*?\)', '', a)))

def parse_part(it):
    m = it.get('_msg') or ''
    if not m or it['blocked']:
        return None
    x = re.search(r'Sperrung der (?:Aus|Zu)fahrt (?:der |von der |aus der )?(' + NM + r')\s+(?:auf|in) (?:die |den |das )?(' + NM + r')([^.]{0,40})', m)
    if x:
        q = x.group(3)
        return {'k': 'aus', 'x': norm(x.group(1)), 'y': norm(x.group(2)),
                'ein': 1 if re.search(r'stadteinw', q) else -1 if re.search(r'stadtausw', q) else 0}
    x = re.search(r'Keine (?:Einfahrt|Zufahrt) (?:aus|von) (?:Richtung |der )?(' + NM + r')', m)
    if x:
        return {'k': 'ein', 'x': addr_street(it), 'y': norm(x.group(1))}
    x = re.search(r'Sperrung der Fahrtrichtung (' + NM + r'|' + PLACE + r')', m) or re.search(r'Fahrtrichtung (' + NM + r'|' + PLACE + r') (?:ist )?gesperrt', m)
    if x:
        return {'k': 'ri', 'x': addr_street(it), 'z': norm(x.group(1))}
    x = re.search(r'Sperrung[^.]{0,140}?(stadteinw|stadtausw)', m)
    if x and not re.search(r'Ampel|LSA|wechselseitig|beide(n)? Richtung', m[x.start():x.end() + 80]):
        return {'k': 'stadt', 'ein': 1 if x.group(1) == 'stadteinw' else -1}
    return None

parts = [(it, pp) for it in items if it['src'] == 'leipzig' for pp in [parse_part(it)] if pp]
print(f'{len(parts)} einseitige Sperrungen im Text erkannt')
n_dir = 0
if parts:
    snames = sorted({n for _, pp in parts for n in (pp.get('x'), pp.get('y'), pp.get('z')) if n})
    rx = '|'.join(re.sub(r'([.$*+?(){}|])', r'[\1]', n) for n in snames if not re.search(r'[\\\[\]^"]', n))
    q = (f'[out:json][timeout:120];(way["highway"]["name"~"^({rx})$"](51.20,12.15,51.48,12.62);'
         f'node["place"]["name"~"^({rx})$"](51.15,12.10,51.55,12.70););out body geom;')
    els = None
    for url in OVERPASS:
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({'data': q}).encode(), headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=150) as r:
                els = json.load(r).get('elements', [])
            break
        except Exception as e:
            print('Overpass', url, e)
    if els is None:
        try:
            old = {i['id']: i for i in json.load(open(dst, encoding='utf-8')).get('items', []) if i.get('dirs')}
        except Exception:
            old = {}
        for it, pp in parts:
            o = old.get(it['id'])
            if o:
                for k in ('dirs', 'line', 'title', 'sub'):
                    it[k] = o[k]
                n_dir += 1
        print(f'Kartendienst nicht erreichbar, {n_dir} Richtungssperrungen aus dem letzten Lauf übernommen')
    else:
        W = {}        # name -> [(nodes, geometry)]
        places = {}
        for el in els:
            nm = el.get('tags', {}).get('name')
            if el['type'] == 'way':
                W.setdefault(nm, []).append((el.get('nodes', []), [(g['lon'], g['lat']) for g in el.get('geometry', [])]))
            elif el['type'] == 'node':
                places[nm] = (el['lon'], el['lat'])

        def nodes_of(nm):
            out = {}
            for ns, gs in W.get(nm, []):
                out.update(zip(ns, gs))
            return out

        def junction(a, b, near):
            na, nb = nodes_of(a), nodes_of(b)
            sh = [(k, na[k]) for k in na.keys() & nb.keys()]
            if not sh:
                return None
            k = min(sh, key=lambda x: mdist(x[1], near))
            return k if mdist(k[1], near) < 400 else None

        def arms(nm, kid, length=70):
            # Linien der Straße nm, die am Knoten kid beginnen (je Richtung eine), bis length Meter lang
            out = []
            for ns, gs in W.get(nm, []):
                for i, n in enumerate(ns):
                    if n != kid:
                        continue
                    for step in (1, -1):
                        seq, j, L = [gs[i]], i + step, 0.0
                        while 0 <= j < len(gs) and L < length:
                            L += mdist(seq[-1], gs[j]); seq.append(gs[j]); j += step
                        if len(seq) >= 2 and L > 25:
                            out.append(seq)
            return out

        def at(seq, m):  # Punkt m Meter entlang der Linie
            L = 0.0
            for a, b in zip(seq, seq[1:]):
                d = mdist(a, b)
                if L + d >= m and d > 0:
                    f = (m - L) / d
                    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
                L += d
            return seq[-1]

        R6 = lambda pt: [round(pt[0], 6), round(pt[1], 6)]
        for it, pp in parts:
            c = (it['lon'], it['lat'])
            dirs = []
            if pp['k'] in ('aus', 'ein'):
                j = junction(pp['x'], pp['y'], c)
                if j:
                    A = arms(pp['x'], j[0])
                    if pp['k'] == 'aus' and pp.get('ein') and len(A) > 1:
                        # stadteinwärts: der Arm, von dem aus man zur Kreuzung hin näher an die Innenstadt kommt
                        sel = [s for s in A if (mdist(s[-1], CENTER) > mdist(s[0], CENTER)) == (pp['ein'] > 0)]
                        A = sel or A
                    for s in A:
                        p1, p2 = at(s, 28), at(s, 55)
                        if pp['k'] == 'aus':
                            dirs.append({'d': round(brg(p2, p1)), 'p': [R6(p2), R6(p1)], 't': f"{pp['x']} → {pp['y']} gesperrt"})
                        else:
                            dirs.append({'d': round(brg(p1, p2)), 'p': [R6(p1), R6(p2)], 't': f"Einfahrt von {pp['y']} in {pp['x']} gesperrt"})
            elif pp['k'] == 'ri':
                j = junction(pp['x'], pp['z'], c)
                tgt = j[1] if j else places.get(pp['z'])
                if tgt and mdist(tgt, c) > 15:
                    dirs.append({'d': round(brg(c, tgt)), 'p': it['poly'], 't': f"{pp['x']}: Richtung {pp['z']} gesperrt"})
            elif pp['k'] == 'stadt':
                b0 = brg(c, CENTER) if pp['ein'] > 0 else brg(CENTER, c)
                dirs.append({'d': round(b0), 'p': it['poly'], 't': 'stadteinwärts gesperrt' if pp['ein'] > 0 else 'stadtauswärts gesperrt'})
            if not dirs:
                print(f"Richtung nicht bestimmbar: {it['title']} {pp}")
                continue
            it['dirs'] = dirs
            it['title'] = 'Einseitige Sperrung: ' + it['title'].split(': ', 1)[1]
            it['sub'] = 'Einseitig gesperrt' + (f" · bis {de(it['end'])}" if it.get('end') else '')
            it['desc'].insert(0, 'Gesperrt: ' + '; '.join(dict.fromkeys(x['t'] for x in dirs)))
            if pp['k'] in ('aus', 'ein') and len(dirs) == 1:
                it['line'] = dirs[0]['p']
            n_dir += 1
            print(f"Einseitig: {it['title']} – " + ', '.join(f"{x['t']} ({x['d']}°)" for x in dirs))
    print(f'{n_dir} einseitige Sperrungen mit Richtung')
for it in items:
    it.pop('_msg', None)

# ---- Autobahn GmbH: Sperrungen von Anschlussstellen (Liste „closure“; dort steht isBlocked oft auf false, obwohl die Rampe zu ist).
# Nur Auf- und Abfahrten, keine Fahrstreifen-Einschränkungen auf der Hauptfahrbahn. Rampenlinie an beiden Enden kürzen,
# damit die Sperrfläche nicht die durchgehende Autobahn oder die Stadtstraße berührt.
n_ab = 0
for road in ['A9', 'A14', 'A38', 'A72', 'A143']:
    try:
        req = urllib.request.Request(f'https://verkehr.autobahn.de/o/autobahn/{road}/services/closure', headers={'User-Agent': UA, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as r:
            cl = json.load(r).get('closure', [])
    except Exception as e:
        print(f'{road}: Sperrungen nicht abrufbar ({e})')
        continue
    for c in cl:
        if str(c.get('future', '')).lower() == 'true':
            continue
        desc = [d.strip() for d in (c.get('description') or []) if isinstance(d, str) and d.strip()]
        txt = ' '.join(desc)
        ramp = re.search(r'\b(Auffahrt|Abfahrt)\b', txt)
        if not ramp and 'Vollsperrung' not in (c.get('title') or '') + txt:
            continue
        g = (c.get('geometry') or {}).get('coordinates') or []
        if g and isinstance(g[0], (int, float)):
            g = [g]
        if not g:
            co = c.get('coordinate') or {}
            try:
                g = [[float(co['long']), float(co['lat'])]]
            except Exception:
                continue
        if not (51.0 <= g[0][1] <= 51.75 and 11.8 <= g[0][0] <= 12.95):
            continue
        k = len(g) // 5 if len(g) >= 6 else 0          # je 20 % an den Enden weglassen
        core = g[k:len(g) - k] if len(g) - 2 * k >= 2 else g
        mid = core[len(core) // 2]
        period = next((d for d in desc if d.startswith('Ende:')), '')
        items.append({'id': 'abc-' + str(c.get('identifier', ''))[-40:], 'src': 'autobahn',
                      'title': 'Sperrung: ' + (ramp.group(1) if ramp else 'Autobahn') + ' ' + re.sub(r'\s+-\s+.*$', '', (c.get('title') or road)).strip(),
                      'sub': (('Rampe gesperrt' if ramp else 'Vollsperrung') + (' · ' + period.replace('Ende: ', 'bis ') if period else '')),
                      'desc': desc[:8], 'lon': round(mid[0], 6), 'lat': round(mid[1], 6),
                      'line': [[round(x, 6), round(y, 6)] for x, y in g], 'poly': [[round(x, 6), round(y, 6)] for x, y in core],
                      'blocked': True})
        n_ab += 1
        n_block += 1
print(f'{n_ab} gesperrte Autobahn-Auf-/Abfahrten')

out = {'updated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
       'source': 'Stadt Leipzig, Verkehrs- und Tiefbauamt: Verkehrsraumeinschränkungen (opendata.leipzig.de); Autobahn GmbH des Bundes (verkehr.autobahn.de)',
       'items': items}
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
for k in sorted(stat):
    print('  ', k, stat[k])
print(f'{len(items)} Einschränkungen geschrieben, davon {n_block} Vollsperrungen, {n_dir} einseitig (von {len(data.get("features", []))})')

"""Baut closures.json: Verkehrsraumeinschränkungen der Stadt Leipzig (Verkehrs- und Tiefbauamt, opendata.leipzig.de, WFS).
Nur heute gültige Einträge, die den Autoverkehr betreffen. Vollsperrungen: blocked=True (die App umfährt sie bei jeder Route).
Aufruf: build_closures.py <ziel.json>"""
import json, sys, re, datetime, urllib.request, urllib.parse, math

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
                  'line': thin(ring), 'poly': thin(ring), 'blocked': bool(full), 'end': e})
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
    print(f'{len(knots)} Kreuzungs-Sperrungen geprüft, {fixed} Lage korrigiert')

out = {'updated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
       'source': 'Stadt Leipzig, Verkehrs- und Tiefbauamt: Verkehrsraumeinschränkungen (opendata.leipzig.de)',
       'items': items}
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
for k in sorted(stat):
    print('  ', k, stat[k])
print(f'{len(items)} Einschränkungen geschrieben, davon {n_block} Vollsperrungen (von {len(data.get("features", []))})')

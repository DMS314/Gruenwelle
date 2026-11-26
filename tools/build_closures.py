"""Baut closures.json: Verkehrsraumeinschränkungen der Stadt Leipzig (Verkehrs- und Tiefbauamt, opendata.leipzig.de, WFS).
Nur heute gültige Einträge, die den Autoverkehr betreffen. Vollsperrungen: blocked=True (die App umfährt sie bei jeder Route).
Aufruf: build_closures.py <ziel.json>"""
import json, sys, re, datetime, urllib.request, math

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
items, n_block = [], 0
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
    if not full and art not in ('Einschränkungen', 'halbseitige Sperrung') and not (msg and CAR.search(msg) and not FOOT.search(msg)):
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

out = {'updated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
       'source': 'Stadt Leipzig, Verkehrs- und Tiefbauamt: Verkehrsraumeinschränkungen (opendata.leipzig.de)',
       'items': items}
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
print(f'{len(items)} Einschränkungen geschrieben, davon {n_block} Vollsperrungen (von {len(data.get("features", []))})')

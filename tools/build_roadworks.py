"""Baut roadworks.json: Autobahn-Baustellen (Autobahn GmbH) + Straßenbaustellen aus OSM (highway=construction).
Aufruf: build_roadworks.py <osm-geojsonseq oder -> <ziel.json> <west,south,east,north>"""
import json, sys, datetime, urllib.request

src, dst = sys.argv[1], sys.argv[2]
W, S, E, N = [float(x) for x in sys.argv[3].split(',')]
UA = 'Gruenwelle-Ampeldaten/1.0 (+https://github.com/DMS314/Gruenwelle)'
inbox = lambda lon, lat: W <= lon <= E and S <= lat <= N
items = []

def thin(coords, maxn=60):
    if len(coords) <= maxn:
        return [[round(x, 6), round(y, 6)] for x, y in coords]
    step = len(coords) / maxn
    out = [coords[int(i * step)] for i in range(maxn)] + [coords[-1]]
    return [[round(x, 6), round(y, 6)] for x, y in out]

# 1) OpenStreetMap: Straßen im Bau
if src != '-':
    try:
        with open(src, encoding='utf-8') as f:
            for line in f:
                line = line.strip('\x1e \n\r')
                if not line:
                    continue
                ft = json.loads(line)
                g = ft.get('geometry') or {}
                if g.get('type') != 'LineString':
                    continue
                c = g['coordinates']
                mid = c[len(c) // 2]
                if not inbox(*mid):
                    continue
                p = ft.get('properties') or {}
                name = p.get('name') or p.get('ref') or 'Straße'
                kind = p.get('construction') or p.get('construction:highway') or ''
                items.append({'id': 'osm-' + str(ft.get('id', '')), 'src': 'osm', 'title': f'Baustelle: {name}',
                              'sub': 'Straße im Bau oder gesperrt' + (f' ({kind})' if kind else ''),
                              'lon': round(mid[0], 6), 'lat': round(mid[1], 6), 'line': thin(c), 'blocked': True})
    except FileNotFoundError:
        pass

# 2) Autobahn GmbH: aktuelle Baustellen
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

n_ab = 0
for road in ['A9', 'A14', 'A38', 'A72', 'A143']:
    try:
        data = get(f'https://verkehr.autobahn.de/o/autobahn/{road}/services/roadworks')
    except Exception as e:
        print(f'{road}: Abruf fehlgeschlagen ({e})')
        continue
    for rw in data.get('roadworks', []):
        try:
            co = rw.get('coordinate') or {}
            lat, lon = float(co.get('lat')), float(co.get('long'))
        except (TypeError, ValueError):
            continue
        if not inbox(lon, lat):
            continue
        geo = rw.get('geometry') or {}
        line = thin(geo['coordinates']) if geo.get('type') == 'LineString' and geo.get('coordinates') else None
        desc = [d for d in (rw.get('description') or []) if isinstance(d, str) and d.strip()]
        items.append({'id': 'ab-' + str(rw.get('identifier', ''))[-40:], 'src': 'autobahn',
                      'title': (rw.get('title') or road).strip(), 'sub': (rw.get('subtitle') or '').strip(),
                      'desc': desc[:6], 'lon': round(lon, 6), 'lat': round(lat, 6), 'line': line,
                      'blocked': str(rw.get('isBlocked', '')).lower() == 'true',
                      'start': rw.get('startTimestamp')})
        n_ab += 1

out = {'updated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
       'source': 'Autobahn GmbH des Bundes (verkehr.autobahn.de); © OpenStreetMap-Mitwirkende, ODbL',
       'items': items}
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
print(f'{len(items)} Baustellen geschrieben ({n_ab} Autobahn, {len(items) - n_ab} OSM)')

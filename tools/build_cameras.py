"""Baut cameras.json: feste Blitzer (highway=speed_camera) mit Fahrtrichtung.

Eingabe: Overpass-JSON (Blitzer + Relationen type=enforcement + deren Knoten),
         osmium-OPL (tags-filter n/highway=speed_camera r/type=enforcement) oder
         osmium-geojsonseq (alte Form, ohne Relationen).

Fahrtrichtung, in dieser Reihenfolge:
  1. Relation type=enforcement: Richtung von Rolle „from“ nach „to“; Messpunkt = Knoten „to“ (liegt auf der Fahrbahn)
  2. Tag direction am Blitzer (Grad oder N/NO/…): Blickrichtung der Kamera, sie schaut dem Verkehr entgegen,
     Fahrtrichtung = direction + 180° (in Leipzig an 38 Blitzern mit Relationen geprüft: Abweichung fast immer ~180°)
  3. unbekannt → beide Richtungen warnen

Ausgabe je Blitzer: [id, lat, lon, maxspeed|null, rot (1 = auch Rotlicht), [[lat, lon, fahrtrichtung|null], …]]
Aufruf: build_cameras.py <eingabe> <ziel.json>
"""
import json, sys, datetime, re, math

src, dst = sys.argv[1], sys.argv[2]
CARD = {'N': 0, 'NNE': 22.5, 'NE': 45, 'ENE': 67.5, 'E': 90, 'ESE': 112.5, 'SE': 135, 'SSE': 157.5, 'S': 180,
        'SSW': 202.5, 'SW': 225, 'WSW': 247.5, 'W': 270, 'WNW': 292.5, 'NW': 315, 'NNW': 337.5,
        'NO': 45, 'NNO': 22.5, 'ONO': 67.5, 'O': 90, 'OSO': 112.5, 'SO': 135, 'SSO': 157.5}


def speed(v):
    m = re.match(r'\s*(\d+)', str(v or ''))
    return int(m.group(1)) if m else None


def bearing(a, b):
    la1, la2, dl = math.radians(a[0]), math.radians(b[0]), math.radians(b[1] - a[1])
    y = math.sin(dl) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def tag_dirs(tags):
    out = []
    for v in str(tags.get('direction') or tags.get('camera:direction') or '').split(';'):
        v = v.strip().upper()
        if not v:
            continue
        try:
            d = float(v)
        except ValueError:
            d = CARD.get(v)
        if d is not None:
            out.append((d + 180) % 360)
    return out


nodes, cams, rels = {}, {}, []   # nodes: id -> (lat, lon, tags)

if src.endswith('.json'):
    for e in json.load(open(src, encoding='utf-8')).get('elements', []):
        if e['type'] == 'node' and 'lat' in e:
            old = nodes.get(e['id'])
            nodes[e['id']] = (e['lat'], e['lon'], e.get('tags') or (old[2] if old else {}))
        elif e['type'] == 'relation':
            rels.append(([(m['type'][0], m['ref'], m.get('role', '')) for m in e.get('members', [])], e.get('tags') or {}))
elif src.endswith('.opl'):
    def dec(s):   # OPL maskiert Sonderzeichen als %hex%
        return re.sub(r'%([0-9a-f]+)%', lambda m: chr(int(m.group(1), 16)), s)

    def kv(s):
        out = {}
        for p in s.split(',') if s else []:
            if '=' in p:
                k, v = p.split('=', 1)
                out[dec(k)] = dec(v)
        return out
    with open(src, encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip('\n').split(' ')
            if not parts or not parts[0]:
                continue
            f0 = {p[0]: p[1:] for p in parts[1:] if p}
            oid = int(parts[0][1:])
            if parts[0][0] == 'n' and f0.get('x') and f0.get('y'):
                nodes[oid] = (float(f0['y']), float(f0['x']), kv(f0.get('T', '')))
            elif parts[0][0] == 'r':
                mem = []
                for m in (f0.get('M') or '').split(','):
                    if '@' in m:
                        ref, role = m.split('@', 1)
                        mem.append((ref[0], int(ref[1:]), dec(role)))
                rels.append((mem, kv(f0.get('T', ''))))
else:   # geojsonseq ohne Relationen
    with open(src, encoding='utf-8') as f:
        for line in f:
            line = line.strip('\x1e \n\r')
            if not line:
                continue
            feat = json.loads(line)
            g, fid = feat.get('geometry') or {}, str(feat.get('id', ''))
            if g.get('type') == 'Point' and fid.startswith('n'):
                lon, lat = g['coordinates']
                nodes[int(fid[1:])] = (lat, lon, feat.get('properties') or {})

for nid, (lat, lon, tags) in nodes.items():
    if tags.get('highway') == 'speed_camera':
        cams[nid] = {'lat': lat, 'lon': lon, 'tags': tags, 'max': speed(tags.get('maxspeed')),
                     'rot': 1 if tags.get('speed_camera') == 'traffic_signals' else 0, 'm': []}

for mem, tags in rels:
    if tags.get('type') != 'enforcement':
        continue
    dev = [r for t, r, role in mem if t == 'n' and role == 'device' and r in cams]
    fr = [r for t, r, role in mem if t == 'n' and role == 'from' and r in nodes]
    to = [r for t, r, role in mem if t == 'n' and role == 'to' and r in nodes]
    for d in dev:
        c = cams[d]
        if tags.get('enforcement') == 'traffic_signals':
            c['rot'] = 1
        if tags.get('enforcement') == 'maxspeed' and speed(tags.get('maxspeed')) and not c['max']:
            c['max'] = speed(tags.get('maxspeed'))
        if to:
            t = nodes[to[0]]
            brg = round(bearing(nodes[fr[0]][:2], t[:2])) % 360 if fr else None
            c['m'].append([round(t[0], 6), round(t[1], 6), brg])

items = []
for nid, c in cams.items():
    pts, seen = [], set()
    for lat, lon, brg in c['m']:   # gleiche Richtung (Tempo- und Rotlicht-Relation) nur einmal
        key = (round(lat, 4), round(lon, 4), None if brg is None else round(brg / 10))
        if key not in seen:
            seen.add(key)
            pts.append([lat, lon, brg])
    if not pts:
        dirs = tag_dirs(c['tags'])
        pts = [[round(c['lat'], 6), round(c['lon'], 6), round(d) % 360] for d in dirs] or [[round(c['lat'], 6), round(c['lon'], 6), None]]
    items.append([nid, round(c['lat'], 6), round(c['lon'], 6), c['max'], c['rot'], pts])

items.sort()
known = sum(1 for it in items if any(p[2] is not None for p in it[5]))
out = {'updated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d'),
       'source': '© OpenStreetMap-Mitwirkende, ODbL',
       'format': 'id,lat,lon,maxspeed,rot,[[lat,lon,fahrtrichtung]]',
       'cameras': items}
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(out, f, separators=(',', ':'))
print(f'{len(items)} feste Blitzer geschrieben, {known} mit Fahrtrichtung')

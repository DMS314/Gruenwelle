"""Baut cameras.json (feste Blitzer, highway=speed_camera) aus osmium-geojsonseq oder Overpass-JSON."""
import json, sys, datetime, re

src, dst = sys.argv[1], sys.argv[2]

def speed(v):
    m = re.match(r'\s*(\d+)', str(v or ''))
    return int(m.group(1)) if m else None

items = {}
def add(osm_id, lat, lon, tags):
    items[osm_id] = [osm_id, round(lat, 6), round(lon, 6), speed(tags.get('maxspeed'))]

if src.endswith('.json'):
    for e in json.load(open(src, encoding='utf-8')).get('elements', []):
        if e.get('type') == 'node' and 'lat' in e:
            add(e['id'], e['lat'], e['lon'], e.get('tags', {}))
else:
    with open(src, encoding='utf-8') as f:
        for line in f:
            line = line.strip('\x1e \n\r')
            if not line:
                continue
            feat = json.loads(line)
            g = feat.get('geometry') or {}
            fid = str(feat.get('id', ''))
            if g.get('type') != 'Point' or not fid.startswith('n'):
                continue
            lon, lat = g['coordinates']
            add(int(fid[1:]), lat, lon, feat.get('properties') or {})

out = {'updated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d'),
       'source': '© OpenStreetMap-Mitwirkende, ODbL',
       'cameras': sorted(items.values())}
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(out, f, separators=(',', ':'))
print(f'{len(out["cameras"])} feste Blitzer geschrieben')

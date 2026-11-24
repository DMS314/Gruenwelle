"""Baut signals.json aus einem osmium-geojsonseq-Export (Ampeln in der Region Leipzig)."""
import json, sys, datetime

src, dst = sys.argv[1], sys.argv[2]
bbox = [float(x) for x in sys.argv[3].split(',')]  # west,south,east,north
nodes = {}
with open(src, encoding='utf-8') as f:
    for line in f:
        line = line.strip('\x1e \n\r')
        if not line:
            continue
        feat = json.loads(line)
        geom = feat.get('geometry') or {}
        if geom.get('type') != 'Point':
            continue
        fid = str(feat.get('id', ''))
        if not fid.startswith('n'):
            continue
        lon, lat = geom['coordinates']
        nodes[int(fid[1:])] = [int(fid[1:]), round(lat, 6), round(lon, 6)]
out = {
    'updated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d'),
    'source': '© OpenStreetMap-Mitwirkende, ODbL',
    'bbox': [bbox[1], bbox[0], bbox[3], bbox[2]],  # south,west,north,east
    'nodes': sorted(nodes.values()),
}
if len(out['nodes']) < 100:
    sys.exit(f'Zu wenige Ampeln gefunden ({len(out["nodes"])}), Datei wird nicht geschrieben')
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(out, f, separators=(',', ':'))
print(f'{len(out["nodes"])} Ampeln geschrieben')

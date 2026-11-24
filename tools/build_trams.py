"""Baut den Straßenbahn-Fahrplan für Leipzig aus dem GTFS-Nahverkehrsfeed (gtfs.de, DELFI, CC BY 4.0).

Aufruf: python3 build_trams.py <gtfs.zip> <zielordner> <west,süd,ost,nord>

Ergebnis:
  trams/stops.json  Haltestellen mit Linien und Koordinaten
  trams/d/<n>.json  Abfahrten je Haltestelle als [Minute, Linie, Ziel, Tage-Bitmaske]
Die Bitmaske gilt ab 'start' (Datum der Erstellung, Ortszeit) für 'days' Tage.
"""
import csv, io, json, math, os, sys, zipfile, datetime, collections, shutil

DAYS = 21
src, dst, bbox_s = sys.argv[1], sys.argv[2], sys.argv[3]
W, S, E, N = [float(x) for x in bbox_s.split(',')]
TRAM_TYPES = {'0', '900', '901', '902', '903', '904', '905', '906'}

try:
    from zoneinfo import ZoneInfo
    today = datetime.datetime.now(ZoneInfo('Europe/Berlin')).date()
except Exception:
    today = datetime.date.today()
dates = [today + datetime.timedelta(days=i) for i in range(DAYS)]
date_idx = {d.strftime('%Y%m%d'): i for i, d in enumerate(dates)}

zf = zipfile.ZipFile(src)
names = {os.path.basename(n): n for n in zf.namelist()}


def rows(name):
    if name not in names:
        return
    with zf.open(names[name]) as f:
        r = csv.reader(io.TextIOWrapper(f, encoding='utf-8-sig', newline=''))
        head = next(r)
        idx = {h.strip(): i for i, h in enumerate(head)}
        yield idx
        for row in r:
            yield row


def table(name):
    it = rows(name)
    if it is None:
        return
    idx = next(it, None)
    if idx is None:
        return
    for row in it:
        yield {k: (row[i] if i < len(row) else '') for k, i in idx.items()}


# Linien
routes = {}
for r in table('routes.txt'):
    if r.get('route_type', '').strip() in TRAM_TYPES:
        short = (r.get('route_short_name') or r.get('route_long_name') or '').strip()
        for p in ('STR ', 'Tram ', 'STR'):
            if short.startswith(p):
                short = short[len(p):].strip()
        col = (r.get('route_color') or '').strip().lstrip('#')
        routes[r['route_id']] = (short or '?', col if len(col) == 6 else '')
print(f'{len(routes)} Straßenbahn-Linien (bundesweit)')

# Haltestellen im Gebiet
stops, parent_of = {}, {}
for s in table('stops.txt'):
    try:
        lat, lon = float(s['stop_lat']), float(s['stop_lon'])
    except (ValueError, KeyError):
        continue
    stops[s['stop_id']] = (s.get('stop_name', '').strip(), lat, lon)
    if s.get('parent_station'):
        parent_of[s['stop_id']] = s['parent_station']
inbox = {sid for sid, (_, la, lo) in stops.items() if S <= la <= N and W <= lo <= E}
print(f'{len(inbox)} Haltepunkte im Gebiet')

# Verkehrstage
svc_mask = collections.defaultdict(int)
WD = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
for c in table('calendar.txt'):
    try:
        a = datetime.datetime.strptime(c['start_date'], '%Y%m%d').date()
        b = datetime.datetime.strptime(c['end_date'], '%Y%m%d').date()
    except (ValueError, KeyError):
        continue
    for i, d in enumerate(dates):
        if a <= d <= b and c.get(WD[d.weekday()], '0').strip() == '1':
            svc_mask[c['service_id']] |= 1 << i
for c in table('calendar_dates.txt'):
    i = date_idx.get(c.get('date', '').strip())
    if i is None:
        continue
    if c.get('exception_type', '').strip() == '1':
        svc_mask[c['service_id']] |= 1 << i
    elif c.get('exception_type', '').strip() == '2':
        svc_mask[c['service_id']] &= ~(1 << i)

# Fahrten der Straßenbahnlinien mit mindestens einem Verkehrstag im Zeitraum
trips = {}
for t in table('trips.txt'):
    rid = t.get('route_id')
    if rid in routes:
        m = svc_mask.get(t.get('service_id'), 0)
        if m:
            trips[t['trip_id']] = (rid, m, (t.get('trip_headsign') or '').strip())
print(f'{len(trips)} Straßenbahn-Fahrten im Zeitraum (bundesweit)')

# Haltezeiten streamen (große Datei): nur Fahrten aus der Liste
per_trip = collections.defaultdict(list)
it = rows('stop_times.txt')
idx = next(it)
ti, si, di, ai, qi = idx['trip_id'], idx['stop_id'], idx.get('departure_time'), idx.get('arrival_time'), idx.get('stop_sequence')
n = 0
for row in it:
    n += 1
    tid = row[ti]
    if tid not in trips:
        continue
    tm = (row[di] if di is not None else '') or (row[ai] if ai is not None else '')
    if not tm:
        continue
    try:
        h, m_, s_ = tm.strip().split(':')
        mins = int(h) * 60 + int(m_)
        seq = int(row[qi]) if qi is not None else len(per_trip[tid])
    except ValueError:
        continue
    per_trip[tid].append((seq, row[si], mins))
print(f'{n} Haltezeiten gelesen, {len(per_trip)} Fahrten mit Haltezeiten')

# Haltestellen gruppieren (Elternhaltestelle, sonst Name)
def gkey(sid):
    p = parent_of.get(sid)
    return p if p else 'n:' + stops[sid][0]


def clean(name):
    for p in ('Leipzig, ', 'Leipzig '):
        if name.startswith(p):
            return name[len(p):]
    return name


groups = {}
deps = collections.defaultdict(lambda: collections.defaultdict(int))
heads = {}
line_ids = {}
lines = []
for tid, lst in per_trip.items():
    lst.sort()
    if not any(sid in inbox for _, sid, _ in lst[:-1]):
        continue  # Fahrt hält nicht im Gebiet
    rid, mask, head = trips[tid]
    short, col = routes[rid]
    if not head:
        last = lst[-1][1]
        head = stops.get(last, ('',))[0]
    head = clean(head)
    if short not in line_ids:
        line_ids[short] = len(lines)
        lines.append([short, col])
    elif col and not lines[line_ids[short]][1]:
        lines[line_ids[short]][1] = col
    li = line_ids[short]
    for k, (seq, sid, mins) in enumerate(lst):
        if k == len(lst) - 1 or sid not in inbox:
            continue  # Endhalt ist keine Abfahrt
        g = gkey(sid)
        if g not in groups:
            groups[g] = {'pts': [], 'lines': set(), 'name': None}
        gr = groups[g]
        gr['pts'].append((stops[sid][1], stops[sid][2]))
        gr['lines'].add(li)
        if gr['name'] is None:
            pn = stops.get(g, (None,))[0] if not g.startswith('n:') else None
            gr['name'] = clean(pn or stops[sid][0])
        hd = heads.setdefault(g, {})
        hi = hd.setdefault(head, len(hd))
        deps[g][(mins, li, hi)] |= mask

if len(groups) < int(os.environ.get('MIN_STOPS', '30')):
    sys.exit(f'Zu wenige Straßenbahn-Haltestellen gefunden ({len(groups)}), nichts geschrieben')

# Linien natürlich sortieren
order = sorted(range(len(lines)), key=lambda i: (int(lines[i][0]) if lines[i][0].isdigit() else 999, lines[i][0]))
remap = {old: new for new, old in enumerate(order)}
lines = [lines[i] for i in order]

tmp = dst + '.tmp'
shutil.rmtree(tmp, ignore_errors=True)
os.makedirs(os.path.join(tmp, 'd'))
out_stops = []
for n_, (g, gr) in enumerate(sorted(groups.items(), key=lambda x: x[1]['name'])):
    la = sum(p[0] for p in gr['pts']) / len(gr['pts'])
    lo = sum(p[1] for p in gr['pts']) / len(gr['pts'])
    out_stops.append([n_, gr['name'], round(la, 6), round(lo, 6), sorted(remap[x] for x in gr['lines'])])
    hl = [h for h, _ in sorted(heads[g].items(), key=lambda x: x[1])]
    d = sorted([m, remap[li], hi, mask] for (m, li, hi), mask in deps[g].items())
    with open(os.path.join(tmp, 'd', f'{n_}.json'), 'w', encoding='utf-8') as f:
        json.dump({'h': hl, 'd': d}, f, separators=(',', ':'), ensure_ascii=False)
meta = {
    'updated': today.isoformat(), 'start': today.isoformat(), 'days': DAYS,
    'source': 'Fahrplan: DELFI e.V. über gtfs.de, CC BY 4.0',
    'lines': lines, 'stops': out_stops,
}
with open(os.path.join(tmp, 'stops.json'), 'w', encoding='utf-8') as f:
    json.dump(meta, f, separators=(',', ':'), ensure_ascii=False)
shutil.rmtree(dst, ignore_errors=True)
os.replace(tmp, dst)
tot = sum(len(v) for v in deps.values())
print(f'{len(out_stops)} Haltestellen, {len(lines)} Linien im Gebiet ({", ".join(l[0] for l in lines)}), {tot} Abfahrtszeilen')

"""Baut mobile.json: amtlich angekündigte mobile Geschwindigkeitskontrollen (Tag + Straße).

Quellen (nur amtlich veröffentlichte, frei nutzbare Daten):
  bonn  Stadt Bonn, Open Data „Messstellen der mobilen Geschwindigkeitsüberwachung“, Wochenliste, CC0
        https://opendata.bonn.de/dataset/messstellen-der-mobilen-geschwindigkeitsüberwachung

Die Straßennamen werden über Overpass in OSM-Linien umgerechnet. Ergebnis je Eintrag:
  items: {"d": "2026-11-23", "s": "bonn", "n": "Reuterstraße"}, Linien je Straße einmal in geo["bonn|Reuterstraße"] = [[lon,lat,lon,lat,...], ...]
Aufruf: build_mobile.py <ziel.json>
"""
import json, re, sys, html, datetime, time, urllib.request, urllib.parse

UA = 'Gruenwelle-Ampeldaten/1.0 (+https://github.com/DMS314/Gruenwelle)'
OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter',
            'https://overpass.private.coffee/api/interpreter']
HW = '^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street)(_link)?$'

SOURCES = {
    'bonn': {'name': 'Stadt Bonn', 'lic': 'CC0', 'area': 'Bonn', 'admin': '6',
             'url': 'https://www.bonn.de/themen-entdecken/verkehr-mobilitaet/mobile-messstellen-aktuelle-woche.php?sp:out=openData.json'},
}


def get(url, data=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8')


def strings(o):
    """Alle Zeichenketten eines JSON-Baums."""
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def clean_street(s):
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s))
    s = re.sub(r'\s+', ' ', s).strip(' ,;')
    s = re.split(r'\s+(?:FR|Fahrtrichtung|stadtein|stadtaus|zw\.|zwischen|Höhe|i\.\s?H\.)\b', s)[0]   # Zusätze abschneiden
    s = re.sub(r'\s*\([^)]*\)', '', s)                       # „(B 9)“ usw.
    s = re.sub(r'([Ss])tr\.(?=\s|$)', r'\1traße', s)         # Abkürzung
    return s.strip(' ,;')


def parse_week_html(text):
    """<h3>Montag, 23.11.2026</h3><ul><li>Straße</li>…</ul> → [(datum, straße)]"""
    out = []
    parts = re.split(r'<h\d[^>]*>(.*?)</h\d>', text, flags=re.S)
    for i in range(1, len(parts) - 1, 2):
        m = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', html.unescape(parts[i]))
        if not m:
            continue
        d = datetime.date(int(m[3]), int(m[2]), int(m[1])).isoformat()
        for li in re.findall(r'<li[^>]*>(.*?)</li>', parts[i + 1], flags=re.S):
            st = clean_street(li)
            if st:
                out.append((d, st))
    return out


def fetch_bonn(src):
    j = json.loads(get(src['url']))
    rows = []
    for s in strings(j):
        if '<li' in s and '<h' in s:
            rows += parse_week_html(s)
    return sorted(set(rows))


def norm(s):
    return re.sub(r'[\s\-]', '', s.lower().replace('ß', 'ss'))


def geocode(src, names):
    """Straßennamen einer Stadt → {name: [linie, …]} über eine Overpass-Abfrage."""
    if not names:
        return {}
    rx = '|'.join(re.sub(r'[()\[\]{}|*+?^$\\"]', '.', n) for n in sorted(names))   # Sonderzeichen als Platzhalter
    q = (f'[out:json][timeout:120];area["boundary"="administrative"]["name"="{src["area"]}"]["admin_level"="{src["admin"]}"]->.a;'
         f'way(area.a)["highway"~"{HW}"]["name"~"^({rx})$",i];out tags geom;')
    j = None
    for u in OVERPASS:
        try:
            j = json.loads(get(u, data=urllib.parse.urlencode({'data': q}).encode(), timeout=180))
            break
        except Exception as e:
            print('Overpass', u, e, file=sys.stderr)
            time.sleep(5)
    if j is None:
        raise RuntimeError('Overpass nicht erreichbar')
    by = {norm(n): n for n in names}
    res = {}
    for w in j.get('elements', []):
        n = by.get(norm((w.get('tags') or {}).get('name', '')))
        g = w.get('geometry') or []
        if n and len(g) >= 2:
            res.setdefault(n, []).append([v for p in g for v in (round(p['lon'], 5), round(p['lat'], 5))])
    return res


def build(dst):
    today = datetime.date.today()
    keep_from = (today - datetime.timedelta(days=1)).isoformat()
    out = {'updated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), 'sources': [], 'items': [], 'geo': {}}
    for sid, src in SOURCES.items():
        info = {'id': sid, 'name': src['name'], 'lic': src['lic'], 'n': 0, 'miss': [], 'state': 'ok'}
        try:
            rows = [r for r in fetch_bonn(src) if r[0] >= keep_from]
            geo = geocode(src, {st for _, st in rows})
            for d, st in rows:
                if st in geo:
                    out['items'].append({'d': d, 's': sid, 'n': st})
                    out['geo'][f'{sid}|{st}'] = geo[st]
                elif st not in info['miss']:
                    info['miss'].append(st)
            info['n'] = sum(1 for it in out['items'] if it['s'] == sid)
            info['days'] = sorted({d for d, _ in rows})
        except Exception as e:
            info['state'] = f'Fehler: {e}'
            print(sid, e, file=sys.stderr)
        out['sources'].append(info)
        print(f"{sid}: {info['n']} Einträge, {len(info['miss'])} ohne Treffer {info['miss'][:10]}, {info['state']}")
    if not out['items'] and any(s['state'] != 'ok' for s in out['sources']):
        try:   # bei Fehlern alte Datei behalten, wenn sie noch Einträge hat
            old = json.load(open(dst, encoding='utf-8'))
            if any(it['d'] >= keep_from for it in old.get('items', [])):
                print('Fehler, alte Datei bleibt'); return
        except Exception:
            pass
    try:   # nur schreiben, wenn sich inhaltlich etwas geändert hat (sonst Commit bei jedem Lauf)
        old = json.load(open(dst, encoding='utf-8'))
        if {k: v for k, v in old.items() if k != 'updated'} == {k: v for k, v in out.items() if k != 'updated'}:
            print('Unverändert'); return
    except Exception:
        pass
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'mobile.json')

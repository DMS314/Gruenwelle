// Grünwelle: Zwischenserver für TomTom-Verkehrsfluss-Kacheln.
// Der TomTom-Schlüssel liegt nur als Secret TOMTOM_KEY in Supabase, nie in der App.
// Aufruf: GET /functions/v1/flow?s=relative0&z=14&x=8755&y=5461
// Schutz des kostenlosen Kontingents (200.000 Kacheln/Monat): gemeinsames Tages-/Monatslimit
// in der Tabelle flow_use (Funktion flow_hit), nur Zoom 10–16, nur Mitteldeutschland,
// 5-Minuten-Zwischenspeicher im Server und Cache-Control für Browser.
const KEY = Deno.env.get('TOMTOM_KEY') ?? '';
const SB_URL = Deno.env.get('SUPABASE_URL') ?? '';
const SB_SVC = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
const DAY_MAX = 6000, MON_MAX = 190000, TTL = 300_000;
const BOX = [10.5, 50.1, 15.1, 52.7]; // West, Süd, Ost, Nord
const STYLES = new Set(['relative0', 'relative0-dark']);
const CORS = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'apikey, authorization, x-client-info, content-type', 'Access-Control-Allow-Methods': 'GET, OPTIONS' };
const mem = new Map<string, { t: number; b: Uint8Array }>();

const lon = (x: number, z: number) => x / 2 ** z * 360 - 180;
const lat = (y: number, z: number) => { const n = Math.PI - 2 * Math.PI * y / 2 ** z; return 180 / Math.PI * Math.atan(Math.sinh(n)); };
const out = (status: number, msg: string) => (status >= 500 && console.error('flow ' + status + ': ' + msg), new Response(msg, { status, headers: { ...CORS, 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } }));
const png = (b: Uint8Array, hit: string) => new Response(b, { headers: { ...CORS, 'content-type': 'image/png', 'cache-control': 'public, max-age=300', 'x-cache': hit } });

async function hit(): Promise<number> {
  const r = await fetch(SB_URL + '/rest/v1/rpc/flow_hit', { method: 'POST', headers: { apikey: SB_SVC, authorization: 'Bearer ' + SB_SVC, 'content-type': 'application/json' }, body: JSON.stringify({ p_day: DAY_MAX, p_mon: MON_MAX }) });
  if (!r.ok) throw new Error('Zähler ' + r.status + ' ' + (await r.text()).slice(0, 200));
  return Number(await r.json());
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS });
  if (req.method !== 'GET') return out(405, 'nur GET');
  if (!KEY) return out(503, 'TOMTOM_KEY fehlt (Secrets: ' + Object.keys(Deno.env.toObject()).filter((k) => !k.startsWith('SUPABASE') && !k.startsWith('SB_') && !k.startsWith('DENO')).join(',') + ')');
  const q = new URL(req.url).searchParams;
  const s = q.get('s') ?? 'relative0', z = Number(q.get('z')), x = Number(q.get('x')), y = Number(q.get('y'));
  if (!STYLES.has(s) || ![z, x, y].every(Number.isInteger) || z < 9 || z > 16 || x < 0 || y < 0 || x >= 2 ** z || y >= 2 ** z) return out(400, 'ungültige Kachel');
  // Kachel muss Mitteldeutschland berühren
  if (lon(x + 1, z) < BOX[0] || lon(x, z) > BOX[2] || lat(y, z) < BOX[1] || lat(y + 1, z) > BOX[3]) return out(400, 'außerhalb');
  const id = `${s}/${z}/${x}/${y}`, now = Date.now(), c = mem.get(id);
  if (c && now - c.t < TTL) return png(c.b, 'mem');
  let n: number;
  try { n = await hit(); } catch (e) { return out(503, String(e)); }
  if (n < 0) return c ? png(c.b, 'alt') : out(429, 'Limit erreicht');
  const r = await fetch(`https://api.tomtom.com/traffic/map/4/tile/flow/${s}/${z}/${x}/${y}.png?key=${encodeURIComponent(KEY)}&tileSize=512&thickness=7`);
  if (!r.ok) return c ? png(c.b, 'alt') : out(r.status === 429 ? 429 : 502, 'TomTom ' + r.status);
  const b = new Uint8Array(await r.arrayBuffer());
  mem.set(id, { t: now, b });
  if (mem.size > 500) mem.delete(mem.keys().next().value!);
  return png(b, 'neu');
});

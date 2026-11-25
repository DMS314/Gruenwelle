import asyncio,json,time
from playwright.async_api import async_playwright
# Karl-Liebknecht-Straße Richtung Süden (Leipzig Südvorstadt)
PTS=[(51.3270+i*-0.00012,12.3750+i*-0.00002) for i in range(25)]
async def main():
 async with async_playwright() as pw:
  b=await pw.chromium.launch(args=['--host-resolver-rules=MAP gw.test 127.0.0.1','--unsafely-treat-insecure-origin-as-secure=http://gw.test:8000'])
  ctx=await b.new_context(geolocation={'latitude':PTS[0][0],'longitude':PTS[0][1],'accuracy':5},permissions=['geolocation'])
  pg=await ctx.new_page();errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
  reqs=[]
  pg.on('requestfinished',lambda r:reqs.append(('ok',r.url[:60],r.method)) if 'interpreter' in r.url else None)
  pg.on('requestfailed',lambda r:reqs.append(('FAIL',r.url[:60],r.failure)) if 'interpreter' in r.url else None)
  async def resp(r):
   if 'interpreter' in r.url:reqs.append(('HTTP',r.status,r.url[:50]))
  pg.on('response',lambda r:asyncio.ensure_future(resp(r)))
  await pg.goto('http://gw.test:8000/index.html');await pg.wait_for_timeout(2000)
  await pg.click('#go');t0=time.time()
  for la,lo in PTS:
   await ctx.set_geolocation({'latitude':la,'longitude':lo,'accuracy':5});await pg.wait_for_timeout(1200)
  st=await pg.evaluate("()=>({state:window.__gw.VL.state,cur:window.__gw.VL.cur,ways:window.__gw.VL.ways?window.__gw.VL.ways.size:0,segs:window.__gw.VL.segs.length,vlim:document.getElementById('vlim').className,n:document.getElementById('vlimN').textContent})")
  print('GPS',await pg.inner_text('#gps'),'| cd',await pg.inner_text('#cd'))
  for u in ['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter','https://overpass.private.coffee/api/interpreter','https://maps.mail.ru/osm/tools/overpass/api/interpreter']:
   r=await pg.evaluate('''async u=>{const t=Date.now();try{const q='[out:json][timeout:25];way(around:300,51.3250,12.3747)[highway];out tags geom;';const ac=new AbortController();setTimeout(()=>ac.abort(),30000);const r=await fetch(u,{signal:ac.signal,method:'POST',body:'data='+encodeURIComponent(q),headers:{'Content-Type':'application/x-www-form-urlencoded'}});const x=await r.text();return [r.status,x.length,Date.now()-t,x.slice(0,120)]}catch(e){return ['ERR',String(e),Date.now()-t]}}''',u)
   print('BROWSER',u,r)
  print('ERGEBNIS',json.dumps(st,ensure_ascii=False),round(time.time()-t0),'s')
  print('OVERPASS',reqs)
  print('FEHLER',errs)
  await b.close()
asyncio.run(main())

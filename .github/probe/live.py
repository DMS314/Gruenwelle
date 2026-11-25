import asyncio,json,time
from playwright.async_api import async_playwright
# Karl-Liebknecht-Straße Richtung Süden (Leipzig Südvorstadt)
PTS=[(51.3270+i*-0.00012,12.3750+i*-0.00002) for i in range(40)]
async def main():
 async with async_playwright() as pw:
  b=await pw.chromium.launch()
  ctx=await b.new_context(geolocation={'latitude':PTS[0][0],'longitude':PTS[0][1],'accuracy':5},permissions=['geolocation'])
  pg=await ctx.new_page();errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
  reqs=[]
  pg.on('requestfinished',lambda r:reqs.append(('ok',r.url[:60],r.method)) if 'interpreter' in r.url else None)
  pg.on('requestfailed',lambda r:reqs.append(('FAIL',r.url[:60],r.failure)) if 'interpreter' in r.url else None)
  async def resp(r):
   if 'interpreter' in r.url:reqs.append(('HTTP',r.status,r.url[:50]))
  pg.on('response',lambda r:asyncio.ensure_future(resp(r)))
  await pg.goto('http://localhost:8000/index.html');await pg.wait_for_timeout(2000)
  await pg.click('#go');t0=time.time()
  for la,lo in PTS:
   await ctx.set_geolocation({'latitude':la,'longitude':lo,'accuracy':5});await pg.wait_for_timeout(1500)
  st=await pg.evaluate("()=>({state:window.__gw.VL.state,cur:window.__gw.VL.cur,ways:window.__gw.VL.ways?window.__gw.VL.ways.size:0,segs:window.__gw.VL.segs.length,vlim:document.getElementById('vlim').className,n:document.getElementById('vlimN').textContent})")
  print('ERGEBNIS',json.dumps(st,ensure_ascii=False),round(time.time()-t0),'s')
  print('OVERPASS',reqs)
  print('FEHLER',errs)
  await b.close()
asyncio.run(main())

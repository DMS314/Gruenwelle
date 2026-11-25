import asyncio,json,time
from playwright.async_api import async_playwright
async def main():
 async with async_playwright() as pw:
  b=await pw.chromium.launch(args=['--host-resolver-rules=MAP gw.test 127.0.0.1','--unsafely-treat-insecure-origin-as-secure=http://gw.test:8000'])
  ctx=await b.new_context(viewport={'width':390,'height':844})
  pg=await ctx.new_page();errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
  await pg.goto('http://gw.test:8000/index.html');await pg.wait_for_timeout(3000)
  await pg.click('#goSim');await pg.wait_for_timeout(8000)
  await pg.click('#pvSim');await pg.click('#simF');await pg.click('#simF')   # 4×
  t0=time.time();last=None;hist=[];k=0
  while time.time()-t0<150:
   st=await pg.evaluate("()=>{const e=document.getElementById('vlim');return e.classList.contains('on')?(document.getElementById('vlimN').textContent+(e.classList.contains('none')?'(frei)':'')+(e.classList.contains('imp')?'(vermutet)':'')):'—'}")
   if st!=last:hist.append(f'{int(time.time()-t0)}s:{st}');last=st
   if k%5==0 and k<60:print(int(time.time()-t0),'s',await pg.evaluate('()=>[window.__gw.VL.state,JSON.stringify(window.__gw.OPS)]'),flush=True)
   k+=1
   if not await pg.evaluate("document.getElementById('simBar').classList.contains('on')"):break
   await pg.wait_for_timeout(1000)
  print('VERLAUF',hist,flush=True)
  print('VL',await pg.evaluate("()=>({state:window.__gw.VL.state,ops:window.__gw.OPS,ways:window.__gw.VL.ways?window.__gw.VL.ways.size:0})"),flush=True)
  print('FEHLER',errs,flush=True)
  await b.close()
asyncio.run(main())

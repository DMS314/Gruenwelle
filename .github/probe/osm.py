import json,urllib.request,urllib.parse,math,sys
US=['https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter']
import time
def q(s):
  for k in range(3):
    for U in US:
      try:
        r=urllib.request.urlopen(urllib.request.Request(U,data=urllib.parse.urlencode({'data':s}).encode(),headers={'User-Agent':'Gruenwelle-Probe (github.com/DMS314/Gruenwelle)'}),timeout=100);return json.loads(r.read())
      except Exception as e:print('  ',U[:30],e,flush=True);time.sleep(3)
  return {'elements':[]}
B='(51.23,12.23,51.45,12.55)'
# 1) Kreuzung Sommerfelder / Zweinaundorfer
j=q('[out:json][timeout:90];way["name"="Sommerfelder Straße"]'+B+'->.s;way["name"="Zweinaundorfer Straße"]'+B+'->.z;node(w.s)(w.z);out;')
X=[(e['lat'],e['lon']) for e in j['elements']];print('KREUZUNG',X)
if X:
  la,lo=X[0]
  j=q(f'[out:json][timeout:90];(node(around:400,{la},{lo})["highway"="speed_camera"];node(around:400,{la},{lo})["enforcement"];node(around:400,{la},{lo})["man_made"="surveillance"];node(around:400,{la},{lo})["speed_camera"];relation(around:400,{la},{lo})["type"="enforcement"];);out body;')
  for e in j['elements']:print('BLITZER?',e['type'],e['id'],e.get('lat'),e.get('lon'),e.get('tags'))
  j=q(f'[out:json][timeout:90];node(around:400,{la},{lo})["highway"="traffic_signals"];out;')
  print('AMPELN',len(j['elements']))
# 2) Permoserstraße / Theodor-Heuss-Straße: Fahrstreifen der Theodor-Heuss-Str. nördlich und Hohentichelnstraße
j=q('[out:json][timeout:90];way["name"="Permoserstraße"]'+B+'->.p;way["name"="Theodor-Heuss-Straße"]'+B+'->.t;node(w.p)(w.t);out;')
P=[(e['lat'],e['lon']) for e in j['elements']];print('PERMOSER',P)
if P:
  la,lo=P[0]
  j=q(f'[out:json][timeout:90];way(around:250,{la},{lo})[highway][name];out tags geom;')
  for w in j['elements']:
    t=w['tags'];g=w['geometry'];
    print('WEG',w['id'],t.get('name'),t.get('highway'),'oneway='+t.get('oneway',''),'lanes='+t.get('lanes',''),{k:v for k,v in t.items() if 'lanes' in k and k!='lanes'},'von',(round(g[0]['lat'],5),round(g[0]['lon'],5)),'bis',(round(g[-1]['lat'],5),round(g[-1]['lon'],5)))

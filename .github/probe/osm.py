import json,urllib.request,urllib.parse,math,time
US=['https://maps.mail.ru/osm/tools/overpass/api/interpreter','https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter']
def q(s):
  for k in range(3):
    for U in US:
      try:return json.loads(urllib.request.urlopen(urllib.request.Request(U,data=urllib.parse.urlencode({'data':s}).encode(),headers={'User-Agent':'Gruenwelle-Probe'}),timeout=100).read())
      except Exception as e:print('  ',U[:30],e,flush=True);time.sleep(3)
def brg(a,b):
  y=math.sin(math.radians(b[1]-a[1]))*math.cos(math.radians(b[0]));x=math.cos(math.radians(a[0]))*math.sin(math.radians(b[0]))-math.sin(math.radians(a[0]))*math.cos(math.radians(b[0]))*math.cos(math.radians(b[1]-a[1]))
  return round((math.degrees(math.atan2(y,x))+360)%360)
J=(51.3275276,12.4377799)
j=q('[out:json][timeout:60];rel(20247818);out body;rel(20247819);out body;>;out body;')
N={e['id']:e for e in j['elements'] if e['type']=='node'}
for e in j['elements']:
  if e['type']=='relation':
    for m in e['members']:
      n=N.get(m['ref']);print('REL',e['id'],e['tags'].get('enforcement'),m['role'],m['ref'],n and (n['lat'],n['lon']),n and n.get('tags'),'Abstand zur Kreuzung',n and round(math.hypot((n['lat']-J[0])*111000,(n['lon']-J[1])*69500)),'m')
j=q(f'[out:json][timeout:60];way(around:30,{J[0]},{J[1]})[highway];out tags geom;')
for w in j['elements']:
  g=[(p['lat'],p['lon']) for p in w['geometry']];t=w['tags']
  # Richtung des Abschnitts, der an der Kreuzung beginnt/endet
  i=min(range(len(g)),key=lambda k:(g[k][0]-J[0])**2+(g[k][1]-J[1])**2)
  out=brg(g[i],g[i+1]) if i+1<len(g) else None; inn=brg(g[i-1],g[i]) if i>0 else None
  print('WEG',w['id'],t.get('name'),t.get('highway'),'oneway='+t.get('oneway',''),'lanes='+t.get('lanes',''),'Richtung weg von Kreuzung (Wegrichtung):',out,'zur Kreuzung hin:',inn,'Ende:',(round(g[-1][0],5),round(g[-1][1],5)))

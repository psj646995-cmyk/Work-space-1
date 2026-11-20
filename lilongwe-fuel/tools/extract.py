import os, sys, json, math, glob, collections, mapbox_vector_tile
src,out=sys.argv[1],sys.argv[2]; z=14; n=2**z
def ll(tx,ty,px,py,ext):
  x=(tx+px/ext)/n; y=(ty+py/ext)/n
  lon=x*360-180; lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*y)))); return [round(lon,5),round(lat,5)]
roads=collections.defaultdict(list); water=[]; rivers=[]; parks=[]; places={}; pois=[]; names=collections.defaultdict(set); aero=[]
RC={'motorway':'trunk','trunk':'trunk','primary':'primary','secondary':'secondary','tertiary':'tertiary','minor':'minor'}
def lines(g):
  if g['type']=='LineString': return [g['coordinates']]
  if g['type']=='MultiLineString': return g['coordinates']
  return []
def polys(g):
  if g['type']=='Polygon': return [g['coordinates']]
  if g['type']=='MultiPolygon': return g['coordinates']
  return []
for f in glob.glob(src+'/*.pbf'):
  tx,ty=map(int,os.path.basename(f)[:-4].split('_'))
  d=mapbox_vector_tile.decode(open(f,'rb').read(),default_options={'y_coord_down':True})
  for lname,L in d.items():
    ext=L.get('extent',4096)
    for ft in L['features']:
      p=ft['properties']; g=ft['geometry']
      cv=lambda cs:[ll(tx,ty,a,b,ext) for a,b in cs]
      if lname=='transportation' and p.get('class') in RC and p.get('brunnel')!='tunnel':
        for l in lines(g): roads[RC[p['class']]].append(cv(l))
      elif lname=='water':
        for pg in polys(g): water.append([cv(r) for r in pg])
      elif lname=='waterway' and p.get('class') in ('river','stream'):
        for l in lines(g): rivers.append(cv(l))
      elif lname=='park' or (lname=='landcover' and p.get('class')=='wood') or (lname=='landuse' and p.get('class') in ('cemetery',)):
        for pg in polys(g): parks.append([cv(r) for r in pg])
      elif lname=='aeroway' and g['type'] in ('Polygon','MultiPolygon'):
        for pg in polys(g): aero.append([cv(r) for r in pg])
      elif lname=='place' and g['type']=='Point':
        nm=p.get('name:latin') or p.get('name')
        if nm: places[nm]={'n':nm,'c':p.get('class'),'p':ll(tx,ty,*g['coordinates'],ext)}
      elif lname=='poi' and g['type']=='Point' and p.get('class')=='fuel':
        pois.append({'n':p.get('name'),'p':ll(tx,ty,*g['coordinates'],ext)})
      elif lname=='transportation_name' and p.get('name'):
        names[p.get('class')].add(p['name'])
# simplify: drop consecutive duplicate points
def dd(l):
  o=[l[0]]
  for q in l[1:]:
    if q!=o[-1]: o.append(q)
  return o
for k in roads: roads[k]=[dd(l) for l in roads[k] if len(dd(l))>1]
data={'roads':roads,'water':water,'rivers':rivers,'parks':parks,'aero':aero,'places':list(places.values())}
json.dump(data,open(out,'w'),separators=(',',':'))
print({k:len(v) for k,v in roads.items()}, len(water),len(rivers),len(parks),len(aero),len(places),'pois',len(pois), os.path.getsize(out))
print(collections.Counter(p['c'] for p in places.values()))
json.dump(pois,open(out+'.pois.json','w'))

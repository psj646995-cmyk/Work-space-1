import math, os, sys, time, json, urllib.request, mapbox_vector_tile
H={'User-Agent':'Mozilla/5.0 lilongwe-fuel-map/1.0'}
outdir=sys.argv[1]; os.makedirs(outdir,exist_ok=True)
tpl=json.load(urllib.request.urlopen(urllib.request.Request('https://tiles.openfreemap.org/planet',headers=H),timeout=30))['tiles'][0]
z=14; S,W,N,E=-14.12,33.63,-13.84,33.90
def t(lat,lon):
  n=2**z; return int((lon+180)/360*n), int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)
x0,y0=t(N,W); x1,y1=t(S,E); print((x1-x0+1)*(y1-y0+1),'tiles')
for x in range(x0,x1+1):
  for y in range(y0,y1+1):
    p=f'{outdir}/{x}_{y}.pbf'
    if os.path.exists(p): continue
    for k in range(3):
      try: open(p,'wb').write(urllib.request.urlopen(urllib.request.Request(tpl.format(z=z,x=x,y=y),headers=H),timeout=30).read()); break
      except Exception as e: print('retry',e); time.sleep(2)
print('ok')

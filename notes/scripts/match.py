"""How much of DineSafe / BodySafe is already in OSM, and what could it add?

Address keys go through accordeur.normalize_street so that "Oakwood Ave" (city
and health-unit spelling) and "Oakwood Avenue" (OSM spelling) are one key.
"""
import csv, json, re, sqlite3, collections, math, zipfile, io
from accordeur import normalize_street
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
D = lambda n: os.path.join(DATA, n)

PC = re.compile(r'([A-Z]\d[A-Z]\s?\d[A-Z]\d)\s*$')
DESIG = re.compile(r',?\s*(?:UNIT|FLR|SUITE|STE|RM|BLDG|FL|LVL|SHOP|KIOSK)[-\s]\s*\S*\s*$', re.I)
NUM = re.compile(r'^(\d+(?:\.\d+)?[A-Za-z]?(?:\s+1/2)?)\s+(.+)$')


def parse_addr(a):
    a = (a or '').strip()
    pc = None
    m = PC.search(a)
    if m:
        pc = m.group(1).replace(' ', '')
        a = a[:m.start()].strip()
    for _ in range(3):
        if a.upper().endswith(' NONE'):
            a = a[:-5].strip()
        else:
            break
    m = DESIG.search(a)
    if m:
        a = a[:m.start()].strip()
    return a.rstrip(' ,'), pc


def akey(num, street):
    if not num or not street:
        return None
    return '%s|%s' % (str(num).upper().replace(' ', ''), normalize_street(street))


def split_key(addr):
    m = NUM.match(addr or '')
    return akey(m.group(1), m.group(2)) if m else None


def hav(lo1, la1, lo2, la2):
    p1, p2 = math.radians(la1), math.radians(la2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


STOP = re.compile(r'\b(inc|ltd|limited|corp|corporation|co|the)\b')


def nname(s):
    s = re.sub(r'[^a-z0-9 ]', ' ', (s or '').lower())
    s = re.sub(r'\b\d{1,4}\b', '', s)
    s = STOP.sub('', s)
    return re.sub(r'\s+', ' ', s).strip()


# ---- city gazetteer, keyed the same way ----
con = sqlite3.connect('file:C:/Users/kk/Code/ontario-address-changes/data/toronto/toronto.db?mode=ro', uri=True)
maxs = con.execute('select max(max_snapshot_id) from addresses').fetchone()[0]
gaz = {}
for num, street, lon, lat in con.execute(
        'select number,street,longitude,latitude from addresses where max_snapshot_id=?', (maxs,)):
    k = akey(num, street)
    if k and k not in gaz:
        gaz[k] = (lon, lat)
print('city address points keyed: %s' % format(len(gaz), ','))


def dinesafe():
    rows = list(csv.DictReader(open(D('ds.csv'), encoding='utf-8-sig')))
    est = {}
    for r in rows:
        k = r['estId']
        if k not in est or r['inspectionDate'] > est[k]['inspectionDate']:
            est[k] = r
    z = zipfile.ZipFile(D('dsh.zip'))
    id2type = {}
    for y in range(2019, 2024):
        t = io.TextIOWrapper(z.open('Dinesafe Historical data/dinesafe_hist_%d.csv' % y),
                             encoding='utf-8-sig', errors='replace')
        for r in csv.DictReader(t):
            id2type[r['Establishment ID']] = r['Establishment Type']
    out = []
    for e in est.values():
        sa, pc = parse_addr(e['address'])
        out.append(dict(id=e['estId'], name=e['estName'], addr=sa, key=split_key(sa), pc=pc,
                        lat=float(e['latitude']), lon=float(e['longitude']),
                        type=id2type.get(e['oldEstId'])))
    return out


def bodysafe():
    d = json.load(open(D('bs.geojson'), encoding='utf-8'))
    est = {}
    for f in d['features']:
        p = f['properties']
        k = str(p['estId'])
        if k not in est or (p['insDate'] or '') > (est[k][0]['insDate'] or ''):
            est[k] = (p, f['geometry'])
    out = []
    for p, g in est.values():
        sa, pc = parse_addr(p['addrFull'])
        lo, la = g['coordinates'][0]
        out.append(dict(id=str(p['estId']), name=p['estName'], addr=sa, key=split_key(sa), pc=pc,
                        lat=la, lon=lo, type=p['srvType']))
    return out


def snap(recs):
    n = 0
    for r in recs:
        g = gaz.get(r['key']) if r['key'] else None
        if g:
            r['glon'], r['glat'] = g
            n += 1
        else:
            r['glon'], r['glat'] = r['lon'], r['lat']
    return n


osm = json.load(open(D('osm.json'), encoding='utf-8'))['elements']
O = []
for e in osm:
    g = e.get('tags', {})
    la = e.get('lat') or (e.get('center') or {}).get('lat')
    lo = e.get('lon') or (e.get('center') or {}).get('lon')
    if la is None:
        continue
    O.append(dict(id='%s/%s' % (e['type'], e['id']), name=g.get('name'),
                  hn=g.get('addr:housenumber'), st=g.get('addr:street'), pc=g.get('addr:postcode'),
                  key=akey(g.get('addr:housenumber'), g.get('addr:street')),
                  kind=('amenity=' + g['amenity']) if 'amenity' in g else 'shop=' + g.get('shop', '?'),
                  lat=la, lon=lo))
n = len(O)
fmt = lambda c: '%s (%.1f%%)' % (format(c, ','), 100.0 * c / n)
print('\nOSM features in bbox: %s' % format(n, ','))
print('  with name            : ' + fmt(sum(1 for o in O if o['name'])))
print('  with addr:housenumber: ' + fmt(sum(1 for o in O if o['hn'])))
print('  with addr:postcode   : ' + fmt(sum(1 for o in O if o['pc'])))
print('  with NO address tags : ' + fmt(sum(1 for o in O if not o['hn'] and not o['pc'])))

CELL = 0.004
grid = collections.defaultdict(list)
for o in O:
    grid[(int(o['lat'] / CELL), int(o['lon'] / CELL))].append(o)


def near(la, lo, r=150):
    k, j = int(la / CELL), int(lo / CELL)
    res = []
    for dk in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for o in grid.get((k + dk, j + dj), ()):
                d = hav(lo, la, o['lon'], o['lat'])
                if d <= r:
                    res.append((o, d))
    return res


by_key = collections.defaultdict(list)
for o in O:
    if o['key']:
        by_key[o['key']].append(o)


def report(label, recs, kinds):
    pool = set(o['id'] for o in O if o['kind'] in kinds)
    print('\n===== %s =====' % label)
    print('  source establishments : %s' % format(len(recs), ','))
    print('  comparable OSM features: %s' % format(len(pool), ','))
    by_a = by_n = none_ = 0
    enrich, missing = [], []
    for r in recs:
        hit = how = None
        if r['key']:
            for o in by_key.get(r['key'], ()):
                if o['id'] in pool:
                    hit, how = o, 'address'
                    break
        if not hit:
            nn = nname(r['name'])
            if nn:
                c = [(o, d) for o, d in near(r['glat'], r['glon'])
                     if o['id'] in pool and o['name'] and nname(o['name']) == nn]
                if c:
                    c.sort(key=lambda x: x[1])
                    hit, how = c[0][0], 'name'
        if how == 'address':
            by_a += 1
        elif how == 'name':
            by_n += 1
            if not hit['hn']:
                enrich.append((r, hit))
        else:
            none_ += 1
            missing.append(r)
    t = len(recs)
    p = lambda c: '%6s (%5.1f%%)' % (format(c, ','), 100.0 * c / t)
    print('  matched by address          : ' + p(by_a))
    print('  matched by name within 150 m: ' + p(by_n))
    print('  total already in OSM        : ' + p(by_a + by_n))
    print('  no OSM counterpart found    : ' + p(none_))
    print('  --> mapped POIs lacking an address this source supplies: %s' % format(len(enrich), ','))
    print('      of those, a postcode too: %s' % format(sum(1 for r, _ in enrich if r['pc']), ','))
    return enrich, missing


DS, BS = dinesafe(), bodysafe()
print('\nDineSafe snapped to a city address point: %s/%s' % (format(snap(DS), ','), format(len(DS), ',')))
print('BodySafe snapped to a city address point: %s/%s' % (format(snap(BS), ','), format(len(BS), ',')))

FOOD = set('''amenity=restaurant amenity=fast_food amenity=cafe amenity=bar amenity=pub
amenity=food_court amenity=ice_cream amenity=biergarten amenity=nightclub shop=bakery shop=butcher
shop=convenience shop=supermarket shop=deli shop=pastry shop=confectionery shop=greengrocer
shop=frozen_food shop=seafood shop=alcohol shop=beverages shop=coffee shop=tea shop=chocolate
shop=health_food shop=farm'''.split())
BODY = set('shop=hairdresser shop=beauty shop=tattoo shop=piercing shop=massage shop=nail'.split())
POI = set(['Restaurant', 'Food Take Out', 'Food Store (Convenience/Variety)', 'Supermarket',
           'Food Court Vendor', 'Bakery', 'Bake Shop', 'Butcher Shop', 'Cocktail Bar / Beverage Room',
           'Cafeteria - Public Access', 'Fish Shop', 'Ice Cream / Yogurt Vendors',
           'Refreshment Stand (Stationary)', 'Banquet Facility', 'Private Club', 'Bed & Breakfast',
           'Brew Your Own Beer / Wine', 'Food Depot', 'Food Bank', 'Hot Dog Cart', 'Food Cart'])

ds_typed = [r for r in DS if r['type'] in POI]
ds_poi = [r for r in DS if r['type'] in POI or r['type'] is None]
report('DineSafe, confirmed POI types only', ds_typed, FOOD)
report('DineSafe, POI types + untyped', ds_poi, FOOD)
e, m = report('BodySafe', BS, BODY)

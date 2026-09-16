"""Qualify the headline numbers: survey queue, 1:1 confidence, duplicate-node risk."""
import collections
import json
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
M = runpy.run_path(os.path.join(HERE, 'match.py'))
DS, BS, O, gaz = M['DS'], M['BS'], M['O'], M['gaz']
by_key, near, nname, FOOD, BODY, POI, hav = (
    M['by_key'], M['near'], M['nname'], M['FOOD'], M['BODY'], M['POI'], M['hav'])
D = lambda n: os.path.join(HERE, 'data', n)

pool = [o for o in O if o['kind'] in FOOD]
poolids = set(o['id'] for o in pool)


def run(recs):
    claimed, enrich = set(), []
    agree = disagree = unnamed = 0
    for r in recs:
        hit = how = None
        if r['key']:
            for o in by_key.get(r['key'], ()):
                if o['id'] in poolids:
                    hit, how = o, 'addr'
                    break
        if not hit:
            nn = nname(r['name'])
            if nn:
                c = [(o, d) for o, d in near(r['glat'], r['glon'])
                     if o['id'] in poolids and o['name'] and nname(o['name']) == nn]
                if c:
                    c.sort(key=lambda x: x[1])
                    hit, how = c[0][0], 'name'
        if not hit:
            continue
        claimed.add(hit['id'])
        if how == 'addr':
            b = nname(hit['name'])
            if not b:
                unnamed += 1
            elif b == nname(r['name']):
                agree += 1
            else:
                disagree += 1
        elif not hit['hn']:
            enrich.append((r, hit))
    return claimed, agree, disagree, unnamed, enrich


ds_typed = [r for r in DS if r['type'] in POI]
ds_poi = [r for r in DS if r['type'] in POI or r['type'] is None]

cl_t, ag, dis, un_, en_t = run(ds_typed)
t = ag + dis + un_
print('\n--- address matches: does the name agree too? (confirmed-POI pass, n=%s) ---' % format(t, ','))
print('  name agrees        : %6s (%.1f%%)' % (format(ag, ','), 100.0 * ag / t))
print('  name disagrees     : %6s (%.1f%%)' % (format(dis, ','), 100.0 * dis / t))
print('  OSM feature unnamed: %6s (%.1f%%)' % (format(un_, ','), 100.0 * un_ / t))

cl_p, _, _, _, en_p = run(ds_poi)
un_typed = len(pool) - len(cl_t)
unmatched = [o for o in pool if o['id'] not in cl_p]
inside = [o for o in unmatched if o['key'] and o['key'] in gaz]
print('\n--- unmatched OSM food POIs, letting UNTYPED DineSafe records claim too ---')
print('  unmatched total: %s   (was %s counting only typed records)'
      % (format(len(unmatched), ','), format(un_typed, ',')))
print('  at a confirmed Toronto address: %s' % format(len(inside), ','))
for k, c in collections.Counter(o['kind'] for o in inside).most_common(8):
    print('    %5d  %s' % (c, k))

print('\n--- enrichment set: records vs distinct OSM targets ---')
for lbl, en in (('confirmed-POI', en_t), ('POI+untyped', en_p)):
    tgt = set(o['id'] for _, o in en)
    print('  %-14s %s records -> %s distinct OSM features' % (lbl, format(len(en), ','), format(len(tgt), ',')))

# ---- duplicate_osm risk: is the address already on the building the node sits in? ----
bld = json.load(open(D('osm_buildings.json'), encoding='utf-8'))['elements']
print('\n--- addressed buildings in bbox: %s ---' % format(len(bld), ','))
CELL = 0.004
bgrid = collections.defaultdict(list)
for b in bld:
    c = b.get('center') or {}
    if 'lat' not in c:
        continue
    b['lat'], b['lon'] = c['lat'], c['lon']
    b['key'] = M['akey'](b['tags'].get('addr:housenumber'), b['tags'].get('addr:street'))
    bgrid[(int(b['lat'] / CELL), int(b['lon'] / CELL))].append(b)

for lbl, en in (('confirmed-POI', en_t), ('POI+untyped', en_p)):
    same = 0
    for r, o in en:
        k, j = int(o['lat'] / CELL), int(o['lon'] / CELL)
        found = False
        for dk in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for b in bgrid.get((k + dk, j + dj), ()):
                    if b['key'] == r['key'] and hav(o['lon'], o['lat'], b['lon'], b['lat']) <= 50:
                        found = True
                        break
                if found:
                    break
            if found:
                break
        same += found
    print('  %-14s %s of %s enrichment targets sit within 50 m of a building ALREADY carrying that address'
          % (lbl, format(same, ','), format(len(en), ',')))
    print('  %-14s -> %s would add a new address, %s would duplicate one'
          % ('', format(len(en) - same, ','), format(same, ',')))

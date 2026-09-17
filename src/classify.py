"""Give every establishment one verdict against OSM, and find the OSM-side orphans.

The verdicts, in the order they are decided:

  not-poi   the archive says this is a kitchen inside a school or a processing
            plant -- licensed, but not a shopfront anyone would map.
  matched   OSM already has this business: the address key agrees and so does the
            name, or the name agrees within 150 m.
  enrich    OSM has the business but no address on it -- we could supply one.
  conflict  OSM has a POI at this address under a different name. Either a
            turnover OSM has not caught, or a venue the address cannot resolve.
  new       nothing in OSM. These are the POIs this data would create.

and separately, over the OSM features:

  orphan    an OSM POI at a confirmed Toronto address that no licence matched.

Address matching gathers every candidate at the key and prefers the one whose name
agrees -- taking the first hit instead is how a restaurant ends up attached to the
convenience store next door.
"""
import collections
import json
import math

from src import config
from src.reduce import address_key, name_key

NAME_RADIUS_M = 150
BUILDING_RADIUS_M = 50
CELL = 0.004  # ~450 m, comfortably over both radii


def metres(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371000 * math.asin(math.sqrt(a))


class Index:
    """Coarse grid over point features, enough for a 150 m neighbourhood query."""

    def __init__(self, items):
        self.cells = collections.defaultdict(list)
        for it in items:
            self.cells[(int(it['lat'] / CELL), int(it['lon'] / CELL))].append(it)

    def near(self, lat, lon, radius):
        k, j = int(lat / CELL), int(lon / CELL)
        out = []
        for dk in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for it in self.cells.get((k + dk, j + dj), ()):
                    d = metres(lon, lat, it['lon'], it['lat'])
                    if d <= radius:
                        out.append((it, d))
        return out


def load_osm(path, want_kinds=True):
    out = []
    with open(path, encoding='utf-8') as fh:
        elements = json.load(fh)['elements']
    for e in elements:
        tags = e.get('tags', {})
        centre = e.get('center') or {}
        lat = e.get('lat', centre.get('lat'))
        lon = e.get('lon', centre.get('lon'))
        if lat is None or lon is None:
            continue
        kind = ('amenity=' + tags['amenity']) if 'amenity' in tags \
            else 'shop=' + tags.get('shop', '?')
        out.append(dict(
            id='%s/%s' % (e['type'], e['id']), name=tags.get('name'),
            housenumber=tags.get('addr:housenumber'), street=tags.get('addr:street'),
            postcode=tags.get('addr:postcode'),
            key=address_key(tags.get('addr:housenumber'), tags.get('addr:street')),
            kind=kind if want_kinds else None, lat=lat, lon=lon, tags=tags,
        ))
    return out


def classify(records, gaz):
    """Attach a verdict to every establishment; return them plus the OSM orphans."""
    osm = load_osm(config.data('osm.json'))
    buildings = load_osm(config.data('osm_buildings.json'), want_kinds=False)

    pools = {'dinesafe': config.FOOD_KINDS, 'bodysafe': config.BODY_KINDS}
    by_key = collections.defaultdict(list)
    for o in osm:
        if o['key']:
            by_key[o['key']].append(o)
    index = Index(osm)
    bld_key = collections.defaultdict(list)
    for b in buildings:
        if b['key']:
            bld_key[b['key']].append(b)

    claimed = set()
    for r in records:
        kinds = pools[r['source']]
        if r['type'] in config.TYPE_INSIDE or (
                r['source'] == 'dinesafe' and r['type'] and r['type'] not in config.TYPE_POI):
            r.update(verdict='not-poi', reason='inside',
                     osm_id=None, osm_name=None, match_m=None, osm_tags=None)
            continue

        mine = name_key(r['name'])
        hit = how = None
        candidates = [o for o in by_key.get(r['key'], ()) if o['kind'] in kinds] if r['key'] else []
        if candidates:
            agreeing = [o for o in candidates if o['name'] and name_key(o['name']) == mine]
            if agreeing:
                hit, how = agreeing[0], 'address+name'
            else:
                named = [o for o in candidates if o['name']]
                other = named[0] if named else candidates[0]
                r.update(verdict='conflict', osm_id=other['id'], osm_name=other['name'],
                         osm_tags=other['tags'],
                         match_m=round(metres(r['alon'], r['alat'],
                                              other['lon'], other['lat']), 1),
                         reason='clash')
                # Like the other matched verdicts, the dot goes on the element a
                # mapper would open -- not on the address point behind it.
                r['alat'], r['alon'] = other['lat'], other['lon']
                claimed.update(o['id'] for o in candidates)
                continue

        if not hit and mine:
            nearby = [(o, d) for o, d in index.near(r['alat'], r['alon'], NAME_RADIUS_M)
                      if o['kind'] in kinds and o['name'] and name_key(o['name']) == mine]
            if nearby:
                nearby.sort(key=lambda x: x[1])
                hit, how = nearby[0][0], 'name+proximity'

        if not hit:
            r.update(verdict='new', reason='none',
                     osm_id=None, osm_name=None, match_m=None, osm_tags=None)
            continue

        claimed.add(hit['id'])
        dist = round(metres(r['alon'], r['alat'], hit['lon'], hit['lat']), 1)
        if hit['housenumber']:
            r.update(verdict='matched', reason='addressed',
                     osm_id=hit['id'], osm_name=hit['name'], match_m=dist,
                     osm_tags=hit['tags'])
        else:
            dup = any(metres(hit['lon'], hit['lat'], b['lon'], b['lat']) <= BUILDING_RADIUS_M
                      for b in bld_key.get(r['key'], ()))
            r.update(verdict='enrich', osm_id=hit['id'], osm_name=hit['name'], match_m=dist,
                     enrich_dup=dup, osm_tags=hit['tags'],
                     reason='dupaddr' if dup else 'noaddr')
        # An enrich/conflict/matched dot belongs on the element a mapper would edit.
        r['alat'], r['alon'] = hit['lat'], hit['lon']

    orphans = []
    wanted = config.FOOD_KINDS | config.BODY_KINDS
    for o in osm:
        if o['id'] in claimed or o['kind'] not in wanted:
            continue
        if o['key'] and o['key'] in gaz:
            orphans.append(o)
    return records, orphans

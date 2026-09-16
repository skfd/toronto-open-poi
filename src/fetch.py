"""Pull everything the explorer is built from into data/.

Five artefacts: the two live feeds, DineSafe's frozen historical archive (the only
surviving source of the establishment category), and two Overpass extracts -- the
POIs to conflate against, and addressed buildings, to tell whether adding an address
to a POI node would merely duplicate the one already on its building.
"""
import json
import os
import time

import requests

from src import config

HEADERS = {'User-Agent': 'toronto-open-poi (github.com/skfd)'}

FOOD_TAGS = (
    'amenity~"^(restaurant|fast_food|cafe|bar|pub|food_court|ice_cream|biergarten|nightclub)$"',
    'shop~"^(bakery|butcher|convenience|supermarket|deli|pastry|confectionery|greengrocer|'
    'frozen_food|seafood|alcohol|beverages|coffee|tea|chocolate|health_food|farm)$"',
)
BODY_TAGS = ('shop~"^(hairdresser|beauty|tattoo|piercing|massage|nail)$"',)
BUILDING_TAGS = ('building"]["addr:housenumber',)


def _ckan_resource(package, predicate):
    r = requests.get('%s/api/3/action/package_show' % config.CKAN,
                     params={'id': package}, timeout=60)
    r.raise_for_status()
    for res in r.json()['result']['resources']:
        if predicate(res):
            return res['url']
    raise LookupError('no resource in %s matched' % package)


def _download(url, name, force=False):
    path = config.data(name)
    if os.path.exists(path) and os.path.getsize(path) and not force:
        print('have %s' % name)
        return path
    print('get  %s' % name)
    r = requests.get(url, timeout=900)
    r.raise_for_status()
    with open(path, 'wb') as fh:
        fh.write(r.content)
    return path


def _bracket(tag):
    key, _, rest = tag.partition('~')
    return '"%s"~%s' % (key, rest) if rest else '"%s"' % key


def _overpass(tags, name, force=False):
    """One extract, rotating mirrors -- the public instance sheds load under 504."""
    path = config.data(name)
    if os.path.exists(path) and os.path.getsize(path) and not force:
        print('have %s' % name)
        return path
    south, west, north, east = config.TORONTO_BBOX
    bbox = '%s,%s,%s,%s' % (south, west, north, east)
    body = ''.join('nwr[%s](%s);' % (_bracket(t), bbox) for t in tags)
    query = '[out:json][timeout:300];(%s);out center tags;' % body
    for attempt in range(6):
        for url in config.OVERPASS_MIRRORS:
            host = url.split('/')[2]
            try:
                r = requests.post(url, data={'data': query}, timeout=300, headers=HEADERS)
                if r.status_code == 200 and r.content[:1] == b'{':
                    with open(path, 'wb') as fh:
                        fh.write(r.content)
                    print('get  %s <- %s (%d elements)'
                          % (name, host, len(json.loads(r.content)['elements'])))
                    return path
                print('  .. %s %s' % (host, r.status_code))
            except requests.RequestException as e:
                print('  .. %s %s' % (host, type(e).__name__))
        time.sleep(20 * (attempt + 1))
    raise RuntimeError('every Overpass mirror refused %s' % name)


def fetch(force=False):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    _download(_ckan_resource('dinesafe', lambda r: r.get('name') == 'Dinesafe.csv'),
              'ds.csv', force)
    _download(_ckan_resource('dinesafe', lambda r: r.get('format') == 'ZIP'),
              'dsh.zip', force)
    _download(_ckan_resource('bodysafe', lambda r: r.get('name') == 'bodysafe - 4326.geojson'),
              'bs.geojson', force)
    _overpass(FOOD_TAGS, 'osm_food.json', force)
    _overpass(BODY_TAGS, 'osm_body.json', force)
    _overpass(BUILDING_TAGS, 'osm_buildings.json', force)

    # Dedup: an element tagged amenity=cafe AND shop=bakery answers both queries.
    # Mirrors also lag each other by a few percent, so both halves come from one run.
    merged = {}
    for name in ('osm_food.json', 'osm_body.json'):
        with open(config.data(name), encoding='utf-8') as fh:
            for e in json.load(fh)['elements']:
                merged[(e['type'], e['id'])] = e
    with open(config.data('osm.json'), 'w', encoding='utf-8') as fh:
        json.dump({'elements': list(merged.values())}, fh)
    print('merged %d distinct OSM POIs' % len(merged))

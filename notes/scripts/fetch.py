"""Pull the four inputs the viability check needs into ./data.

Nothing here is the capture layer — it is the throwaway that measured whether one
is worth building. Resource ids were read from CKAN package_show on 2026-09-16.
"""
import json
import os
import time

import requests

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
CKAN = 'https://ckan0.cf.opendata.inter.prod-toronto.ca'
BBOX = '43.58,-79.64,43.86,-79.11'

OVERPASS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
    'https://overpass.osm.ch/api/interpreter',
]
HDRS = {'User-Agent': 'toronto-open-poi viability check'}

FOOD_TAGS = ('amenity~"^(restaurant|fast_food|cafe|bar|pub|food_court|ice_cream|biergarten|nightclub)$"',
             'shop~"^(bakery|butcher|convenience|supermarket|deli|pastry|confectionery|greengrocer|'
             'frozen_food|seafood|alcohol|beverages|coffee|tea|chocolate|health_food|farm)$"')
BODY_TAGS = ('shop~"^(hairdresser|beauty|tattoo|piercing|massage|nail)$"',)


def ckan_resource(package, predicate):
    """URL of the first resource of `package` whose dict satisfies `predicate`."""
    r = requests.get('%s/api/3/action/package_show' % CKAN, params={'id': package}, timeout=60)
    r.raise_for_status()
    for res in r.json()['result']['resources']:
        if predicate(res):
            return res['url']
    raise LookupError('no matching resource in %s' % package)


def download(url, name):
    path = os.path.join(DATA, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        print('have %s' % name)
        return path
    print('get  %s' % name)
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    with open(path, 'wb') as fh:
        fh.write(r.content)
    return path


def overpass(tags, name):
    """Fetch one Overpass extract, rotating mirrors — the public instance sheds load."""
    path = os.path.join(DATA, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        print('have %s' % name)
        return path
    body = ''.join('nwr[%s](%s);' % (_bracket(t), BBOX) for t in tags)
    query = '[out:json][timeout:240];(%s);out center tags;' % body
    for attempt in range(6):
        for url in OVERPASS:
            try:
                r = requests.post(url, data={'data': query}, timeout=300, headers=HDRS)
                if r.status_code == 200 and r.content[:1] == b'{':
                    n = len(json.loads(r.content)['elements'])
                    with open(path, 'wb') as fh:
                        fh.write(r.content)
                    print('get  %s <- %s (%d elements)' % (name, url.split('/')[2], n))
                    return path
                print('  .. %s %s' % (url.split('/')[2], r.status_code))
            except requests.RequestException as e:
                print('  .. %s %s' % (url.split('/')[2], type(e).__name__))
        time.sleep(20 * (attempt + 1))
    raise RuntimeError('every Overpass mirror refused %s' % name)


def _bracket(tag):
    key, _, rest = tag.partition('~')
    return '"%s"~%s' % (key, rest)


def main():
    os.makedirs(DATA, exist_ok=True)
    download(ckan_resource('dinesafe', lambda r: r.get('name') == 'Dinesafe.csv'), 'ds.csv')
    download(ckan_resource('dinesafe', lambda r: r.get('format') == 'ZIP'), 'dsh.zip')
    download(ckan_resource('bodysafe', lambda r: r.get('name') == 'bodysafe - 4326.geojson'), 'bs.geojson')
    overpass(FOOD_TAGS, 'osm_food.json')
    overpass(BODY_TAGS, 'osm_body.json')
    # Dedup: an element tagged both amenity=cafe and shop=bakery answers both queries.
    # Mirrors also lag each other by a few percent, so keep the two halves from one run.
    merged = {}
    for name in ('osm_food.json', 'osm_body.json'):
        for e in json.load(open(os.path.join(DATA, name), encoding='utf-8'))['elements']:
            merged[(e['type'], e['id'])] = e
    with open(os.path.join(DATA, 'osm.json'), 'w', encoding='utf-8') as fh:
        json.dump({'elements': list(merged.values())}, fh)
    print('merged %d distinct OSM elements' % len(merged))


if __name__ == '__main__':
    main()

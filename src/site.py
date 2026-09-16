"""Render site/explorer/ -- the candidate GeoJSON plus the page that reads it."""
import collections
import json
import os
import shutil
from datetime import date

from src import config
from src.reduce import restore_case

EXPLORER_DIR = os.path.join(config.SITE_DIR, 'explorer')


def _feature(rec):
    props = dict(
        src=rec['source'], id=rec['est_id'], verdict=rec['verdict'],
        name=rec['name'], readable=rec['name_readable'],
        addr=restore_case(rec['addr']), unit=rec['unit'], postcode=rec['postcode'],
        type=rec['type'], tag=_osm_tag(rec),
        inspected=rec['last_inspection'], status=rec['status'],
        venue=rec['venue_size'], snapped=rec['snapped'], reason=rec['reason'],
        osm=rec['osm_id'], osm_name=rec['osm_name'], m=rec['match_m'],
    )
    if rec.get('enrich_dup'):
        props['dup'] = True
    if not rec['certain']:
        props['unknown'] = True
    if rec.get('also_licensed_as'):
        props['twins'] = len(rec['also_licensed_as'])
    return dict(type='Feature', properties={k: v for k, v in props.items() if v not in (None, '')},
                geometry=dict(type='Point', coordinates=[round(rec['alon'], 6),
                                                         round(rec['alat'], 6)]))


def _osm_tag(rec):
    if rec['source'] == 'bodysafe':
        parts = [config.SRV_TO_OSM.get(t) for t in (rec['type'] or '').split(' + ')]
        seen = [p for p in dict.fromkeys(parts) if p]
        return ' / '.join(seen) or None
    return config.TYPE_TO_OSM.get(rec['type'])


def _orphan_feature(o):
    return dict(type='Feature', properties=dict(
        src='osm', verdict='orphan', name=o['name'], osm=o['id'], tag=o['kind'],
        addr=' '.join(x for x in (o['housenumber'], o['street']) if x),
        postcode=o['postcode'],
        reason='mapped in OSM at a Toronto address, but no licence matches it',
    ), geometry=dict(type='Point', coordinates=[round(o['lon'], 6), round(o['lat'], 6)]))


def build(records, orphans):
    os.makedirs(EXPLORER_DIR, exist_ok=True)
    feats = [_feature(r) for r in records] + [_orphan_feature(o) for o in orphans]
    counts = collections.Counter(f['properties']['verdict'] for f in feats)
    with open(os.path.join(EXPLORER_DIR, 'candidates.geojson'), 'w', encoding='utf-8') as fh:
        json.dump(dict(type='FeatureCollection', features=feats), fh)

    creatable = sum(1 for f in feats if f['properties']['verdict'] == 'new'
                    and f['properties'].get('venue', 1) < config.VENUE_THRESHOLD
                    and not f['properties'].get('unknown'))
    with open(os.path.join(config.ASSETS_DIR, 'explorer.html.tmpl'), encoding='utf-8') as fh:
        html = fh.read()
    for token, value in (
            ('NEW', counts['new']), ('ENRICH', counts['enrich']),
            ('CONFLICT', counts['conflict']), ('MATCHED', counts['matched']),
            ('NOTPOI', counts['not-poi']), ('ORPHAN', counts['orphan']),
            ('CREATABLE', creatable), ('TOTAL', len(feats)),
            ('BUILD_DATE', date.today().isoformat())):
        html = html.replace('{{%s}}' % token,
                            '{:,}'.format(value) if isinstance(value, int) else value)
    with open(os.path.join(EXPLORER_DIR, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(html)
    for name in ('explorer.css', 'explorer.js'):
        shutil.copy(os.path.join(config.ASSETS_DIR, name), os.path.join(EXPLORER_DIR, name))

    print('%s features -> %s' % ('{:,}'.format(len(feats)), EXPLORER_DIR))
    for v in config.VERDICTS:
        print('  %-9s %6s' % (v, '{:,}'.format(counts[v])))
    print('  %-9s %6s  (new, category known, outside a >=%d-premise venue)'
          % ('creatable', '{:,}'.format(creatable), config.VENUE_THRESHOLD))
    return counts

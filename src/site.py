"""Render site/explorer/ -- the candidate GeoJSON plus the page that reads it."""
import collections
import json
import os
import shutil
from datetime import date

from src import config, tags
from src.reduce import restore_case

EXPLORER_DIR = os.path.join(config.SITE_DIR, 'explorer')

# Why a premise landed where it did. The page holds the prose; shipping a code
# per feature instead of the sentence saves about a megabyte.
REASONS = {
    'inside': 'licensed premise inside or behind another POI',
    'none': 'no OSM feature at this address or by this name',
    'addressed': 'OSM already has this business, with an address',
    'noaddr': 'OSM has this business but no address on it',
    'dupaddr': 'the building here already carries this address',
    'clash': 'OSM has a POI at this address, none by this name',
    'orphan': 'mapped in OSM at a Toronto address, but no licence matches it',
}


def _feature(rec, tag_index):
    """One candidate, with its tag comparison encoded against the shared legend."""
    diff = [[tag_index(tag), osm, src, state]
            for tag, osm, src, state in tags.compare(rec, rec.get('osm_tags'))]
    props = dict(
        src=rec['source'], id=rec['est_id'], verdict=rec['verdict'],
        name=rec['name'], readable=rec['name_readable'],
        addr=restore_case(rec['addr']), unit=rec['unit'], postcode=rec['postcode'],
        type=rec['type'], diff=diff,
        inspected=rec['last_inspection'], status=rec['status'],
        venue=rec['venue_size'], snapped=rec['snapped'], reason=rec['reason'],
        osm=rec['osm_id'], m=rec['match_m'],
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


def _orphan_feature(o, tag_index):
    return dict(type='Feature', properties=dict(
        src='osm', verdict='orphan', name=o['name'], osm=o['id'], kind=o['kind'],
        diff=[[tag_index(k), v, None, tags.OSM_ONLY] for k, v in sorted(o['tags'].items())
              if k in config.OSM_TAGS_KEPT],
        addr=' '.join(x for x in (o['housenumber'], o['street']) if x),
        reason='orphan',
    ), geometry=dict(type='Point', coordinates=[round(o['lon'], 6), round(o['lat'], 6)]))


def build(records, orphans):
    os.makedirs(EXPLORER_DIR, exist_ok=True)
    legend = []
    seen = {}

    def tag_index(tag):
        if tag not in seen:
            seen[tag] = len(legend)
            legend.append(tag)
        return seen[tag]

    feats = ([_feature(r, tag_index) for r in records]
             + [_orphan_feature(o, tag_index) for o in orphans])
    counts = collections.Counter(f['properties']['verdict'] for f in feats)
    with open(os.path.join(EXPLORER_DIR, 'candidates.geojson'), 'w', encoding='utf-8') as fh:
        json.dump(dict(type='FeatureCollection', tagLegend=legend,
                       reasons=REASONS, features=feats), fh)

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

    mb = os.path.getsize(os.path.join(EXPLORER_DIR, 'candidates.geojson')) / 1e6
    print('%s features, %.1f MB -> %s' % ('{:,}'.format(len(feats)), mb, EXPLORER_DIR))
    for v in config.VERDICTS:
        print('  %-9s %6s' % (v, '{:,}'.format(counts[v])))
    print('  %-9s %6s  (new, category known, outside a >=%d-premise venue)'
          % ('creatable', '{:,}'.format(creatable), config.VENUE_THRESHOLD))
    return counts

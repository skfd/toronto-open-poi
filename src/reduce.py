"""Rows to establishments.

Both feeds publish one row per inspection x infraction; a POI is an establishment.
This collapses them, parses the address, recovers the category DineSafe dropped
upstream in 2023, and anchors each premise to a City address point where one matches.
"""
import collections
import csv
import io
import json
import re
import sqlite3
import zipfile

from accordeur import normalize_street

from src import config

PC = re.compile(r'([A-Z]\d[A-Z]\s?\d[A-Z]\d)\s*$')
DESIG = re.compile(r',?\s*((?:UNIT|FLR|SUITE|STE|RM|BLDG|FL|LVL|SHOP|KIOSK)[-\s]\s*\S*)\s*$', re.I)
NUM = re.compile(r'^(\d+(?:\.\d+)?[A-Za-z]?(?:\s+1/2)?)\s+(.+)$')

# Words that stay lowercase when restoring case, and ones that stay shouted.
_SMALL = frozenset('a an and at by de for in la le of on or the to von van'.split())
_KEEP_UPPER = frozenset('BBQ BQ CN GTA KFC LCBO PJ TD USA VIP Q1 II III IV'.split())


def parse_address(raw):
    """-> (street address, unit, postcode). Both feeds use the same layout.

    Legacy rows put the unit before a ``None`` placeholder
    (``21 DALHOUSIE ST, Flr-MAIN None M5B 2A5``); post-migration rows do not
    (``65 Front St W Unit-442 M5J 1E6``).
    """
    a = (raw or '').strip()
    pc = unit = None
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
        unit = m.group(1).strip()
        a = a[:m.start()].strip()
    return a.rstrip(' ,'), unit, pc


def address_key(number, street):
    """House number + street collapsed so "Oakwood Ave" and "Oakwood Avenue" agree."""
    if not number or not street:
        return None
    return '%s|%s' % (str(number).upper().replace(' ', ''), normalize_street(street))


def split_key(street_address):
    m = NUM.match(street_address or '')
    return address_key(m.group(1), m.group(2)) if m else None


def restore_case(name):
    """A readable rendering of a SHOUTED name. A hint for a mapper, never a tag."""
    if not name or name != name.upper():
        return name
    out = []
    for i, word in enumerate(re.split(r'(\s+)', name)):
        if not word.strip():
            out.append(word)
            continue
        bare = word.strip('.,()&-')
        if bare in _KEEP_UPPER or (len(bare) <= 3 and not bare.isalpha()):
            out.append(word)
        elif i and bare.lower() in _SMALL:
            out.append(word.lower())
        else:
            out.append(re.sub(r"[A-Za-z][A-Za-z']*",
                              lambda m: m.group(0)[0] + m.group(0)[1:].lower(), word.title()))
    return ''.join(out)


def gazetteer():
    """address key -> (lon, lat) from the City address points already on disk."""
    con = sqlite3.connect('file:%s?mode=ro' % config.GAZETTEER_DB.replace('\\', '/'), uri=True)
    latest = con.execute('select max(max_snapshot_id) from addresses').fetchone()[0]
    gaz = {}
    for number, street, lon, lat in con.execute(
            'select number,street,longitude,latitude from addresses where max_snapshot_id=?',
            (latest,)):
        key = address_key(number, street)
        if key and key not in gaz:
            gaz[key] = (lon, lat)
    con.close()
    return gaz


def _archive_types():
    """oldEstId -> Establishment Type, from the frozen 2001-2023 archive.

    Only the last five years are read: the type is a property of the premise, and
    a 2004 row would resurrect a category for a licence that has since turned over.
    """
    types = {}
    with zipfile.ZipFile(config.data('dsh.zip')) as z:
        for year in range(2019, 2024):
            name = 'Dinesafe Historical data/dinesafe_hist_%d.csv' % year
            with z.open(name) as fh:
                text = io.TextIOWrapper(fh, encoding='utf-8-sig', errors='replace')
                for row in csv.DictReader(text):
                    types[row['Establishment ID']] = row['Establishment Type']
    return types


def _latest(rows, key_of, date_of):
    """Keep one row per establishment: newest inspection, id as a stable tiebreak."""
    best = {}
    for r in rows:
        k = key_of(r)
        rank = (date_of(r) or '', str(r.get('_id') or ''))
        if k not in best or rank > best[k][0]:
            best[k] = (rank, r)
    return [v[1] for v in best.values()]


def dinesafe():
    with open(config.data('ds.csv'), encoding='utf-8-sig') as fh:
        rows = list(csv.DictReader(fh))
    types = _archive_types()
    out = []
    for r in _latest(rows, lambda x: x['estId'], lambda x: x['inspectionDate']):
        addr, unit, pc = parse_address(r['address'])
        out.append(dict(
            source='dinesafe', est_id=r['estId'], legacy_id=r['oldEstId'],
            name=r['estName'], addr=addr, unit=unit, postcode=pc, key=split_key(addr),
            lat=float(r['latitude']), lon=float(r['longitude']),
            type=types.get(r['oldEstId']), last_inspection=r['inspectionDate'],
            status=r['inspectionStatus'],
        ))
    return out


def bodysafe():
    with open(config.data('bs.geojson'), encoding='utf-8') as fh:
        feats = json.load(fh)['features']
    rows = [dict(f['properties'], _geom=f['geometry']) for f in feats]
    by_est = collections.defaultdict(set)
    for r in rows:
        by_est[str(r['estId'])].add(r['srvType'])
    out = []
    for r in _latest(rows, lambda x: str(x['estId']), lambda x: x['insDate'] or ''):
        addr, unit, pc = parse_address(r['addrFull'])
        lon, lat = r['_geom']['coordinates'][0]
        est = str(r['estId'])
        out.append(dict(
            source='bodysafe', est_id=est, legacy_id=est,
            name=r['estName'], addr=addr, unit=unit, postcode=pc, key=split_key(addr),
            lat=lat, lon=lon,
            type=' + '.join(sorted(by_est[est])), last_inspection=r['insDate'],
            status=r['insStatus'],
        ))
    return out


STOPWORDS = re.compile(r'\b(inc|ltd|limited|corp|corporation|co|the)\b')


def name_key(name):
    """Names compared with punctuation, unit numbers and shell-company noise gone.

    Used both to collapse one premise's several licences and to decide whether an
    OSM feature is the same business, so the two can never drift apart.
    """
    s = re.sub(r'[^a-z0-9 ]', ' ', (name or '').lower())
    s = re.sub(r'\b\d{1,4}\b', '', s)
    return re.sub(r'\s+', ' ', STOPWORDS.sub('', s)).strip()


def _collapse_twins(recs):
    """One premise per (address, name), not one per licence id.

    The 2025 CRM migration re-keyed part of DineSafe from a numeric id to a
    Salesforce one without retiring the old rows, so ~830 premises appear twice
    under the same name and address. A re-licence at the same address does the
    same thing. Either way OSM would map one shopfront, so keep the newest.
    """
    groups = collections.defaultdict(list)
    loose = []
    for r in recs:
        if r['key']:
            groups[(r['source'], r['key'], name_key(r['name']))].append(r)
        else:
            loose.append(r)
    kept = []
    for rows in groups.values():
        rows.sort(key=lambda r: ((r['last_inspection'] or ''), r['est_id']), reverse=True)
        head = rows[0]
        head['also_licensed_as'] = [r['est_id'] for r in rows[1:]] or None
        kept.append(head)
    return kept + loose


def establishments():
    """Both feeds, deduplicated, address-anchored, with venue size attached."""
    recs = _collapse_twins(dinesafe() + bodysafe())
    gaz = gazetteer()
    at_key = collections.Counter(r['key'] for r in recs if r['key'])
    for r in recs:
        anchor = gaz.get(r['key']) if r['key'] else None
        r['snapped'] = anchor is not None
        r['alon'], r['alat'] = anchor if anchor else (r['lon'], r['lat'])
        r['venue_size'] = at_key.get(r['key'], 1)
        r['name_readable'] = restore_case(r['name'])
        # DineSafe's category is only recoverable for premises the frozen archive
        # still covers; everything licensed since 2024 has none, anywhere.
        r['certain'] = r['source'] == 'bodysafe' or r['type'] is not None
    return recs, gaz

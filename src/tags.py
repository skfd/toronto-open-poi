"""Put both sides in OSM shape and say where they differ.

The source is a licensing record, not a map feature, so "what would this look like
as OSM tags" is a translation with judgement in it. Keeping that translation here,
rather than in the page, means the comparison the explorer draws and any future
conflation agree by construction.
"""
import re

from accordeur import collapse_conventions, expand_street_name

from src import config
from src.reduce import NUM, name_key, restore_case

# How a row of the comparison table reads.
# One character each: a comparison row is repeated ~130,000 times across the file.
SAME = 's'           # the two agree outright
CONV = 'c'           # they agree once spelling conventions collapse
DIFF = 'd'           # both sides have a value and the values disagree
ADD = 'a'            # only the licence has it -- what an edit would contribute
OSM_ONLY = 'o'       # only OSM has it -- nothing to do, shown for context

_PHONE = re.compile(r'\D')

# The source packs two different things into one designator slot.
_FLOOR_PREFIXES = ('flr', 'fl', 'lvl')


def phone(raw):
    """Toronto ten-digit strings to the OSM/E.164-ish form mappers use here."""
    digits = _PHONE.sub('', raw or '')
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return '+1 %s-%s-%s' % (digits[:3], digits[3:6], digits[6:])


def _category(rec):
    """The shop/amenity tags the licence implies. Several trades -> the most specific."""
    if rec['source'] == 'bodysafe':
        merged, shops = {}, []
        for srv in (rec['type'] or '').split(' + '):
            for k, v in config.SRV_TO_OSM.get(srv, {}).items():
                if k == 'shop':
                    shops.append(v)
                else:
                    merged.setdefault(k, v)
        for candidate in config.SHOP_PRECEDENCE:
            if candidate in shops:
                merged['shop'] = candidate
                break
        else:
            if shops:
                merged['shop'] = shops[0]
        # beauty=* only makes sense alongside shop=beauty.
        if merged.get('shop') != 'beauty':
            merged.pop('beauty', None)
        # One feature, one primary tag: the trade wins over the clinic reading that
        # Injectable Personal Services alone would give.
        if 'shop' in merged:
            merged.pop('amenity', None)
        return merged
    return dict(config.TYPE_TO_OSM.get(rec['type'], {}))


def source_tags(rec):
    """The licence rendered as the tags a mapper would most likely write."""
    tags = {}
    if rec['name']:
        tags['name'] = rec['name_readable']
    m = NUM.match(restore_case(rec['addr'] or ''))
    if m:
        tags['addr:housenumber'] = m.group(1)
        tags['addr:street'] = expand_street_name(m.group(2)) or m.group(2)
    if rec['unit']:
        # "Unit-442" is addr:unit; "Flr-MAIN" is a storey, and calling it a unit
        # would put "MAIN" where a mapper expects a suite number.
        prefix, _, bare = rec['unit'].partition('-')
        bare = bare.strip()
        if bare and bare.lower() != 'none':
            key = 'addr:floor' if prefix.strip().lower() in _FLOOR_PREFIXES else 'addr:unit'
            tags[key] = bare.title() if bare.isupper() and bare.isalpha() else bare
    if rec['postcode']:
        pc = rec['postcode']
        tags['addr:postcode'] = '%s %s' % (pc[:3], pc[3:]) if len(pc) == 6 else pc
    tags.update(_category(rec))
    tel = phone(rec.get('phone'))
    if tel:
        tags['phone'] = tel
    return tags


def _state(tag, osm_value, src_value):
    if osm_value and src_value:
        if osm_value == src_value:
            return SAME
        if tag == 'name':
            return CONV if name_key(osm_value) == name_key(src_value) else DIFF
        if tag == 'addr:street':
            return CONV if collapse_conventions(osm_value) == collapse_conventions(src_value) \
                else DIFF
        if tag == 'addr:postcode':
            return CONV if osm_value.replace(' ', '').upper() == src_value.replace(' ', '').upper() \
                else DIFF
        if osm_value.strip().lower() == src_value.strip().lower():
            return CONV
        return DIFF
    if src_value:
        return ADD
    return OSM_ONLY


def compare(rec, osm_tags):
    """One row per tag either side carries, ordered, with a state each."""
    src = source_tags(rec)
    osm = {k: v for k, v in (osm_tags or {}).items() if k in config.OSM_TAGS_KEPT}
    order = list(config.COMPARE_TAGS)
    order += [k for k in sorted(osm) if k not in order]
    rows = []
    for tag in order:
        o, s = osm.get(tag), src.get(tag)
        if not o and not s:
            continue
        rows.append([tag, o, s, _state(tag, o, s)])
    return rows

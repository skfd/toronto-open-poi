"""Paths, bounds, and the vocabularies the classifier and the site share."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
SITE_DIR = os.path.join(ROOT, 'site')
ASSETS_DIR = os.path.join(ROOT, 'assets')

# The address tracker this project borrows the city gazetteer from. Read-only.
GAZETTEER_DB = r'C:\Users\kk\Code\ontario-address-changes\data\toronto\toronto.db'

# [south, west, north, east] -- the same clip toronto-import-beholder uses.
TORONTO_BBOX = (43.58, -79.64, 43.86, -79.11)

CKAN = 'https://ckan0.cf.opendata.inter.prod-toronto.ca'

OVERPASS_MIRRORS = (
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
    'https://overpass.osm.ch/api/interpreter',
)

# OSM tags a DineSafe premise could plausibly already be mapped as.
FOOD_KINDS = frozenset('''
amenity=restaurant amenity=fast_food amenity=cafe amenity=bar amenity=pub amenity=food_court
amenity=ice_cream amenity=biergarten amenity=nightclub shop=bakery shop=butcher shop=convenience
shop=supermarket shop=deli shop=pastry shop=confectionery shop=greengrocer shop=frozen_food
shop=seafood shop=alcohol shop=beverages shop=coffee shop=tea shop=chocolate shop=health_food
shop=farm'''.split())

BODY_KINDS = frozenset(
    'shop=hairdresser shop=beauty shop=tattoo shop=piercing shop=massage shop=nail'.split())

# DineSafe establishment types, from the 2001-2023 archive -- the live feed carries none.
# Split by whether the premise is its own OSM feature.
TYPE_POI = frozenset([
    'Restaurant', 'Food Take Out', 'Food Store (Convenience/Variety)', 'Supermarket',
    'Food Court Vendor', 'Bakery', 'Bake Shop', 'Butcher Shop', 'Cocktail Bar / Beverage Room',
    'Cafeteria - Public Access', 'Fish Shop', 'Ice Cream / Yogurt Vendors',
    'Refreshment Stand (Stationary)', 'Banquet Facility', 'Private Club', 'Bed & Breakfast',
    'Brew Your Own Beer / Wine', 'Food Depot', 'Food Bank', 'Hot Dog Cart', 'Food Cart',
])
TYPE_INSIDE = frozenset([
    'Child Care - Catered', 'Child Care - Food Preparation', 'Student Nutrition Site',
    'Cafeteria - Private Access', 'Retirement Homes(Licensed)', 'Retirement Homes(Un-licensed)',
    'Nursing Home / Home for the Aged', 'Rest Home', 'Boarding / Lodging Home - Kitchen',
    'Institutional Food Services', 'Secondary School Food Services',
    'Elementary School Food Services', 'College / University Food Services',
    'Other Educational Facility Food Services', 'Hospitals & Health Facilities',
    'Church Banquet Facility', 'Community Kitchen (Meal Program)', 'Serving Kitchen',
])

# The OSM tag a DineSafe type would most likely become. Only a starting point for a
# mapper -- the source says what is licensed, not what the shopfront says.
TYPE_TO_OSM = {
    'Restaurant': 'amenity=restaurant',
    'Food Take Out': 'amenity=fast_food',
    'Food Store (Convenience/Variety)': 'shop=convenience',
    'Supermarket': 'shop=supermarket',
    'Food Court Vendor': 'amenity=fast_food',
    'Bakery': 'shop=bakery',
    'Bake Shop': 'shop=bakery',
    'Butcher Shop': 'shop=butcher',
    'Cocktail Bar / Beverage Room': 'amenity=bar',
    'Cafeteria - Public Access': 'amenity=cafeteria',
    'Fish Shop': 'shop=seafood',
    'Ice Cream / Yogurt Vendors': 'amenity=ice_cream',
    'Refreshment Stand (Stationary)': 'amenity=fast_food',
    'Banquet Facility': 'amenity=events_venue',
    'Private Club': 'amenity=social_club',
    'Bed & Breakfast': 'tourism=guest_house',
    'Brew Your Own Beer / Wine': 'shop=brewing_supplies',
    'Food Depot': 'social_facility=food_bank',
    'Food Bank': 'social_facility=food_bank',
    'Hot Dog Cart': 'amenity=fast_food',
    'Food Cart': 'amenity=fast_food',
}

# BodySafe srvType -> OSM. Near 1:1; only the injectables case is genuinely unclear.
SRV_TO_OSM = {
    'Barbering & Hairdressing': 'shop=hairdresser',
    'Tattooing': 'shop=tattoo',
    'Body Piercing': 'shop=piercing',
    'Ear Piercing': 'shop=piercing',
    'Nails': 'shop=beauty + beauty=nails',
    'Aesthetics': 'shop=beauty',
    'Micropigmentation/Microblading': 'shop=beauty',
    'Injectable Personal Services': 'amenity=clinic (uncertain)',
}

# A shared address hosting this many premises is a venue -- a mall or food court that
# OSM models as one feature, not as N shopfronts.
VENUE_THRESHOLD = 5

VERDICTS = ('new', 'enrich', 'conflict', 'matched', 'not-poi', 'orphan')


def data(name):
    return os.path.join(DATA_DIR, name)

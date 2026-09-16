# Is this data shape viable for OSM enrichment?

Measured 2026-09-16 against live pulls of both sources, the City of Toronto address
points already in `ontario-address-changes/data/toronto/toronto.db` (snapshot 126), and a
fresh Overpass extract of Toronto food and personal-service POIs.

**Short answer: yes, and the address is worth more than the POI.** DineSafe is a better
street-address-and-postcode source than the address dataset this project's siblings already
import into OSM. As a POI source it is usable but needs work: two thirds of it is already
mapped, the category was dropped upstream in 2023, and the names are shouted.

Reproduce with `scripts/fetch.py` then `scripts/match.py`.

## Inputs, as pulled

| | DineSafe | BodySafe |
|---|---|---|
| rows (one per inspection × infraction) | 116,954 | 13,993 |
| establishments, reduced to latest inspection | 18,996 | 3,760 |
| inspection dates covered | 2023-11-10 → 2026-09-15 | 2022-04-12 → 2026-09-15 |
| published as | CSV / JSON / XML, identical 18 fields | GeoJSON 4326, SHP, GPKG, CSV |
| geometry | `latitude`/`longitude` on every row | MultiPoint, no nulls |
| category field | **none** (dropped upstream) | `srvType`, 8 values |
| refresh | daily | daily |

Plus `Dinesafe Historical Data`, an 11 MB ZIP of 23 frozen per-year CSVs, 2001–2023, one
consistent schema — and that schema **has** the `Establishment Type` the live feed lost.

## Address quality: the strongest part

| | DineSafe | BodySafe |
|---|---|---|
| resolves to a City address point | **93.8%** | 84.5% |
| median offset from that point | 1.3 m | 1.1 m |
| within 5 m | 62.0% | 69.9% |
| p90 offset | 48.1 m | 29.7 m |
| carries a postcode | **97.8%** | 0% |
| carries a unit / floor designator | 4,281 | ~1,100 |
| coordinates outside the city bbox | **0** | 0 |

The address string is machine-structured — `<number> <street> <unit-or-None> <postcode>` —
and parses cleanly once you know legacy rows put the unit *before* the `None` slot
(`21 DALHOUSIE ST, Flr-MAIN None M5B 2A5`) while post-migration rows do not
(`65 Front St W Unit-442 M5J 1E6`). Only 10 of 18,996 lack a house number.

**The coordinate is the weak field, not the address.** Median offset is 1.3 m but only 62%
are within 5 m, so roughly a third of the points were geocoded some other way — parcel or
block centroid. Conflation should match on the address key and then *anchor to the city
address point*, discarding the source coordinate.

Street names need `accordeur.normalize_street` on both sides: the health units write
`Oakwood Ave`, OSM writes `Oakwood Avenue`. Without it the address match rate reads 1.6%
instead of 50.8% — an easy way to talk yourself out of this project.

## It also enriches the address layer, not just OSM

Toronto's address points model **no postcode and no unit** — the `unit` column is `None`
for all 525,438 rows. On the 17,356 establishments sitting on a known city address point,
DineSafe supplies:

- **11,083 distinct address→postcode pairs**, with only **18** addresses giving
  conflicting postcodes (0.16%)
- 4,038 unit designators for points that carry none

This needs no OSM, no conflation and no category. It is the cheapest real product here.

## How much is actually a POI

Recovering the dropped type from the 2019–2023 archive covers 12,663 of 18,996 (66.7%):

| | count | share of typed |
|---|---|---|
| its own OSM feature (Restaurant 5,130, Food Take Out 1,982, convenience 822, supermarket 408, food-court vendor 348, bakery 303 …) | **10,422** | 82.3% |
| a kitchen *inside* another POI — child care, student nutrition, nursing home, hospital, school cafeteria | 1,862 | 14.7% |
| not a POI at all — processing plants, caterers, catering vehicles, CNE stalls | 379 | 3.0% |

Extrapolated to the untyped remainder: **~15,600 mappable POIs**, not 19,000.

Establishments licensed after the 2023 archive freeze have no category anywhere. That set
grows every day the capture layer does not exist.

## Against OSM

Overpass, bbox `[43.58, -79.64, 43.86, -79.11]`, food + personal-service tags:

```
OSM features in bbox   16,772
  with name            16,419  (97.9%)
  with addr:housenumber 8,465  (50.5%)
  with addr:postcode    3,002  (17.9%)
  with NO address tags  8,282  (49.4%)
```

Taken from `overpass-api.de`. Mirrors lag each other — an extract pulled minutes
later from a secondary mirror differed by ~4% in both directions, so pull both halves
from one run.

DineSafe, confirmed-POI types only (10,420 establishments) against 13,920 OSM food POIs:

| | count | share |
|---|---|---|
| matched by address key | 5,295 | 50.8% |
| matched by name within 150 m | 1,551 | 14.9% |
| **already in OSM** | **6,846** | **65.7%** |
| no OSM counterpart found | 3,574 | 34.3% |

BodySafe against 2,831 OSM personal-service POIs: 897 by address (23.9%), 367 by name
(9.8%), **33.6% already in OSM**, 2,496 with no counterpart.

### The mall problem is real and is the main conflation risk

Those 6,846 matches land on only **4,687 distinct OSM features**. 3,878 of them (82.7%) are
claimed by exactly one establishment — trustworthy 1:1. But **2,968 establishments pile onto
a shared feature**: 46 onto one `Manchu Wok`, 46 onto a `McDonald's`, 41 onto a
`Chick-fil-A`. These are food courts where the address key is the mall and OSM models one
node. 6 addresses host 50+ establishments each; 2,381 host 2–4.

Any conflation has to treat a multi-establishment address as a venue and fall back to
name matching inside it, or it will confidently attach the wrong licence to the wrong node.

### What could be added

- **1,296 already-mapped food POIs carry no `addr:housenumber` and name-match a DineSafe
  establishment** — 1,260 of those come with a postcode too. That is the import-grade
  enrichment set, and postcode is a genuine gift since the city address points have none.
- **318 personal-service POIs** likewise from BodySafe (no postcodes there).
- **2,682 OSM food POIs sit at a confirmed Toronto address with no DineSafe counterpart** —
  823 restaurants, 625 fast food, 401 cafés, 252 convenience. Either closed, mis-tagged, or
  a licence this pull missed. A survey queue, not an import.
- A further 5,614 unmatched OSM food POIs have no address tags at all, so they cannot be
  placed either way without geometry work.

## Frictions to plan around

**Names are a matching hint, not an importable tag.** 89.2% are ALL CAPS. Case restoration
is lossy on things like `A-OK Cafe (Aritzia)`. 852 carry venue/branch suffixes —
`100 Level - STAND 116 - TIM HORTONS`, `ALBION HILLS FARM - QE 623 - CNE 2024`,
`ALEXANDER STIRLING PUBLIC SCHOOL - SNP - MORNING MEAL`. Chains dominate and match easily:
380 Tim Hortons, 176 Subway, 92 Pizza Pizza, 83 Starbucks, 80 McDonald's.

**Churn is high, so a static import rots.** Within the ~3-year window the live file covers,
3,135 establishments (16.5%) were first seen in the last 12 months and 3,004 (15.8%) have
not been inspected in the last 12. The second figure conflates closure with a low-risk
inspection cadence — DineSafe inspects 1–3× a year by risk — so read it as an upper bound.
Either way the change feed is worth more than the snapshot.

**An id migration is in flight.** `estId` comes in two shapes: legacy numeric (3,468
establishments, all dated ≤ 2025-11-07) and Salesforce (`001Vo000013QjdPIAS`, 15,528).
849 legacy ids fan out to two current ids with the same name, address and dates — the
migration re-keyed some establishments' history and duplicated 3,269 rows. 2,196
establishments have `oldEstId` literally `"None"`. This is happening now and only
snapshots will record it.

## Licence: not a blocker

CKAN reports `license_id: notspecified` for both packages — but it reports the same for
`address-points-municipal-toronto-one-address-repository`, the dataset this project's
siblings already import into OSM. 292 of 557 portal packages say `notspecified`; the field
is unmaintained. All three dataset *pages* state **Open Government Licence – Toronto**.
Same footing as the existing import. Worth one written confirmation before an import-grade
upload, not before building.

## Verdict, ranked by value per unit of work

1. **Postcodes and units for the address layer.** 11,083 address→postcode pairs at a 0.16%
   contradiction rate, on points already imported. No conflation, no category, no names.
2. **BodySafe as a POI source.** Keeps its category, crosswalks near 1:1
   (Barbering & Hairdressing → `shop=hairdresser`, Tattooing → `shop=tattoo`, Body/Ear
   Piercing → `shop=piercing`, Nails → `shop=beauty` + `beauty=nails`,
   Aesthetics/Micropigmentation → `shop=beauty`; only Injectable Personal Services, n=5, is
   ambiguous). 1,553 of 3,760 offer more than one service — the `beauty=*` multi-value case.
   Two thirds are not in OSM at all.
3. **Address + postcode onto already-mapped food POIs.** 1,296 candidates, high confidence
   because they name-match and the address resolves to a city point.
4. **DineSafe as a new-POI source.** Workable but needs the venue rule, name case
   restoration, and the archive join for categories. Do it last.

Nothing here argues against capture. Findings 3 (churn) and the id migration argue that
capture should start before the design is finished.

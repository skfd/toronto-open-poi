# toronto-open-poi

Toronto open POI data. **Start with capturing and accumulating DineSafe and BodySafe data.**

"Start with" is the load-bearing word. DineSafe (restaurant inspections) and BodySafe
(personal-service settings — tattoo, piercing, nail, barber) are the first two sources,
not the scope. The project is Toronto's open data as a POI corpus; these two are where
the capture-and-accumulate machinery gets built and proven.

**Capturing and accumulating** is the verb pair that matters. Read here as — and this is a
reading, not something checked: the city publishes a current view and overwrites it, nobody
keeps the history, so this project pulls on a schedule and keeps every dated pull forever.
Then you can later ask when a place opened, when it closed and what it was called at the
time. Whether the portal already retains history is listed below as unconfirmed; if it does,
open question 1 gets a different answer.

## Open questions

Decisions deliberately not made yet. Decide them on purpose.

1. **What "accumulate" means.** Dated full snapshots, or a diffed change log, or both?
   DineSafe is an inspection log — its rows naturally pile up over time on their own. But
   establishments open, close and rename, and *that* history only exists in the difference
   between snapshots. The POI value is in the second thing.
2. **Own store, or reuse `address-vault`.** `~/Code/address-vault` is already a tiered
   hot/cold snapshot store with a restic backend and a dated-read API, built for city
   address dumps. Is this a second consumer of that library, a fork of the pattern, or
   something smaller?
3. **What the POI output is for.** A dataset that sits there, an OSM conflation feed, a
   beholder-style watcher that reports changes, a MapRoulette challenge? This decides the
   shape of everything downstream and nothing upstream, so it can wait — but not forever.
4. **What comes after these two.** Which Toronto open datasets are POI-shaped enough to
   join this? Naming a few now would tell you whether the capture layer should be generic
   or hand-written per source.
5. **Identity across snapshots.** Does DineSafe give a stable establishment id that survives
   a rename or a change of operator? If not, matching a place to itself across years is the
   hard part of the project and should be found out early.

## Leads — unverified, found by name only, evaluate before using

- **open.toronto.ca** — Toronto's CKAN open data portal. DineSafe and BodySafe are both
  believed to be published there, with an API. Not opened; confirm the dataset ids, the
  licence, the update cadence and whether history is retained upstream.
- **`~/Code/address-vault`** — tiered snapshot store (hot disk + cold restic), library-as-API,
  no HTTP server. The closest existing thing to what this project needs. Not opened beyond
  its README summary.
- **`~/Code/ontario-address-changes`** — the change-tracker pattern, a consumer of the vault.
  If this project ends up reporting *changes* rather than serving snapshots, read this first.
- **`~/Code/poi-categories`** — an Overture→OSM category crosswalk. Relevant only if the
  output turns out to be OSM-facing.
- **`~/Code/toronto-import-beholder`**, **`toronto-parks-layer`** — sibling Toronto repos;
  may already hold portal-fetching code worth stealing.

## The explorer

```
python run.py fetch     # both feeds, DineSafe's frozen archive, two Overpass extracts
python run.py build     # reduce, classify against OSM, render site/explorer/
python run.py serve     # http://127.0.0.1:8777/explorer/
```

![The explorer over downtown Toronto: red dots are premises with no OSM counterpart, teal
are mapped POIs missing an address, orange are addresses where OSM knows a different
name.](docs/explorer.png)

Every licensed premise gets one verdict against OpenStreetMap, and the map shows what
acting on it would mean:

| | |
|---|---|
| **would create** | nothing in OSM at this address or by this name — a POI this data would add |
| **would address** | OSM has the business but no `addr:*`; we could supply street, unit and postcode |
| **name conflict** | OSM has a POI at this address under a different name — a turnover it missed, or a mall the address cannot resolve |
| **already in OSM** | address and name both agree, or the name agrees within 150 m |
| **OSM, unlicensed** | mapped at a confirmed Toronto address with no licence behind it — closed, mis-tagged, or missed |
| **not a POI** | a kitchen inside a school, nursing home or processing plant |

The filters open on the defensible subset: **4,982 premises** that are unmatched, whose
category is known, and that do not share a mall or stadium address with four others. All
9,423 unmatched are there behind the toggles, and the counts follow whatever you filter to.

Click a row to centre it, then <kbd>O</kbd> opens that spot on openstreetmap.org and
<kbd>I</kbd> in the iD editor — on the matched element where there is one, at the City
address point where there is not. Hollow dots are premises absent from the City gazetteer,
so they sit on the health unit's own geocode, which the survey found to be off by tens of
metres about a third of the time. Pale dots are premises whose category DineSafe dropped in
2023 and the archive cannot recover.

**It is a survey queue, not an import.** Nothing here has been checked against the ground.

## Status

Measured, and explorable. `notes/osm-viability.md` answers whether these two feeds can
enrich OSM, from live pulls rather than from the leads below — including the licence
question, which turns out not to be a blocker. Read it before deciding the open questions;
several of them it answers outright. `notes/scripts/` is the frozen record of that survey;
`src/` is the working version of the same logic.

Next step when the project earns it: `/gh-init` from inside this folder for a GitHub remote.

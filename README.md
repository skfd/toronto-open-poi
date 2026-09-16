# toronto-open-poi

Toronto open POI data. **Start with capturing and accumulating DineSafe and BodySafe data.**

"Start with" is the load-bearing word. DineSafe (restaurant inspections) and BodySafe
(personal-service settings — tattoo, piercing, nail, barber) are the first two sources,
not the scope. The project is Toronto's open data as a POI corpus; these two are where
the capture-and-accumulate machinery gets built and proven.

**Capturing and accumulating** is the verb pair that matters. The city publishes a current
view and overwrites it. Nobody keeps the history. This project pulls on a schedule and keeps
every dated pull forever, so that later you can ask when a place opened, when it closed, and
what it was called at the time — questions the live file cannot answer.

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

## Status

Empty. Nothing built yet. This README is the whole repo.

Next step when the project earns it: `/gh-init` from inside this folder for a GitHub remote.

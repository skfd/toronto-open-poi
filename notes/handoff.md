# Handoff — what I would look at next, and what I am uneasy about

Written 2026-09-17, at the point where the explorer went public at
<https://skfd.github.io/toronto-open-poi/>. Everything below is honest about whether
it is measured or suspected; where a number would settle it, the number is here or
the command that gets it is.

---

## Blocking anyone but me from building this

**`config.GAZETTEER_DB` is an absolute path into a sibling repo.**

```python
GAZETTEER_DB = r'C:\Users\kk\Code\ontario-address-changes\data\toronto\toronto.db'
```

The repo is public now and nobody else can run `build`. The gazetteer is doing one
job — address key → coordinate — and `ontario-address-changes` got it from a City
GeoJSON that `fetch` could pull directly. Either fetch the address points like the
other three inputs, or make the path an env var with a clear failure message. The
first is better: it removes the sibling dependency entirely.

**A cold run has never been done.** `fetch` has only ever short-circuited on files
copied in from the survey. The CKAN predicates resolve and `_bracket` builds valid
Overpass, both checked — but `rm -rf data/ && python run.py fetch` end to end has not
been. Do that before telling anyone to clone it.

**No tests.** Four real bugs in `restore_case`, `parse_address`, `_twin_key` and
`tags.source_tags` were caught by looking at screenshots, which is not a method.
These are pure functions over strings; they deserve a test file more than anything
else here does. `L. A. SALON`, `MCDONALD'S`, `Flr-MAIN`, `21 DALHOUSIE ST, Flr-MAIN
None M5B 2A5`, `A&W` are the cases that already bit.

---

## Measured, and worth acting on

### 1,081 "conflicts" are name refinements, not conflicts

Of 4,881 conflicts with a named OSM feature:

| | count | share |
|---|---|---|
| OSM name is a subset of the licence name (`3 Eggs` ← `3 EGGS ALL DAY PUB & GRILL`) | 726 | 14.9% |
| licence name is a subset of the OSM name | 355 | 7.3% |
| share a word, neither contains the other | 691 | 14.2% |
| **no words in common** — genuinely a different business | **3,109** | **63.7%** |

So a fifth of the conflict bucket is one business under two spellings, and the tag
diff already makes that visible case by case. A `refine` verdict — "same place, OSM's
name is shorter" — would move 1,081 out of `conflict` and give a mapper a distinct,
easy, low-risk task. The 63.7% with no overlap are the interesting residue: turnover
OSM missed, or a mall the address key cannot resolve.

Token containment over `name_key` is the whole test; `notes/` has the one-off that
produced the table above.

### `name_key` does not fold `&` into `and`

`A&W` normalises to `a w`, `A and W` to `a and w`, so they do not match and the pair
lands in `conflict`. Seen in the refinement sample above. Cheap fix in
`reduce.name_key`; unmeasured how many pairs it moves, but ampersands are everywhere
in restaurant names so it is probably worth more than it looks.

### Phone numbers are 95% unique, and 5% are not

Fixed the worst of it before handing over: `000-000-0000` (56 premises) and
`416-000-0000` (40) were being published as `phone` tags. `tags.phone` now rejects
NANP-invalid area/exchange codes and repeated-digit subscriber parts.

What remains is legitimate but needs care: **700 numbers are shared across 1,846
premises** — a franchise head office, a property manager, a catering company running
several kitchens. `+1 647-407-9036` covers 25 differently-named premises. Tagging a
shared number onto a shopfront is not obviously right. Consider suppressing `phone`
where the number appears on more than ~3 premises, or flagging it in the popup.

---

## Suspected, not measured

**`new` is inflated by premises whose category we cannot recover.** 6,333 DineSafe
premises have no type — the archive froze in 2023 — and they are all treated as
possible POIs. Some fraction are caterers, school kitchens and processing plants that
the classifier would have sent to `not-poi` if it knew. The `Include unknown
category` filter is off by default for exactly this reason, but the underlying number
is unknown and **grows every day**, because every new licence since 2024 lands in it.
A sample of 100 checked by hand against the ground would give a correction factor and
would be an afternoon's work.

**The venue threshold of 5 is arbitrary.** 2,381 addresses host 2–4 premises and get
no special handling, yet that is exactly where the address key can attach a
restaurant to the convenience store next door. Preferring the name-agreeing candidate
helps, and moved 361 records from `conflict` to `matched` when introduced — but its
accuracy at 2–4 premises per address has not been checked.

**`enrich_dup` is a proxy, not containment.** The 159 flagged are nodes within 50 m of
a *building centroid* carrying the same address key. In a large building the centroid
is further than 50 m from the shopfront node, so the real count is probably higher.
`toronto-import-beholder` does point-in-polygon properly; borrow it rather than
reinventing.

**Unsnapped premises may be the most interesting ones.** ~1,700 DineSafe and ~580
BodySafe do not resolve to a City address point and sit on the health-unit geocode,
p90 ≈ 48 m off. They render hollow. But a premise whose address the City gazetteer
does not know is disproportionately likely to be a *new* address — a new build, a
re-numbering — which is exactly what a POI layer wants to catch. Worth a second pass
with fuzzier street matching before writing them off as noise.

---

## The thing this project was actually for, still unbuilt

The README's first line is **"capturing and accumulating"**. The explorer is a
current-state tool; nothing keeps history yet. Open questions 1 and 2 are still open.

The survey found a reason to hurry: **DineSafe's CRM migration is in flight right
now**, re-keying premises from numeric ids to Salesforce ones, unevenly, and
duplicating some of their history. 839 premises are currently the same shopfront
filed twice. That transition is only observable in the difference between snapshots,
and nobody is taking any. `address-vault` already does tiered dated snapshots and
needs one small generalisation — a `csv` format alongside `geojson` — to take these
feeds.

Other things worth building, roughly in order of value per unit of work:

1. **Postcodes and units back to the address layer.** 11,083 address→postcode pairs
   at a 0.16% contradiction rate, on points already imported to OSM, where the City
   models no postcode at all. No conflation, no categories, no names. Still the
   cheapest real product here and still unbuilt.
2. **A weekly rebuild.** Both feeds refresh daily; the published page is a fixed
   snapshot and starts drifting immediately. Siblings use a GitHub Action or
   `schedule-add.ps1`. Whichever, the page should show the OSM extract date
   separately from the build date — right now one date implies both are fresh.
3. **MapRoulette export.** The `new` and `enrich` sets are already the right shape,
   and MapRoulette gives per-task review, which is the honest way to use this.
4. **The `orphan` layer as a closure detector.** 1,069 OSM POIs at a confirmed
   Toronto address with no licence behind them. Cross-referenced against DineSafe's
   last-inspection dates, that is a "probably closed, please survey" list — useful to
   OSM in a way nothing else here is, because it removes rather than adds.
5. **Permalinks.** `#lat=..&z=..&verdict=new` so a finding can be sent to someone.

---

## Things I decided that you might decide differently

- **Filters open on the defensible subset** — category known, not a venue stall —
  which shows ~5,000 of 9,452 unmatched. That is a claim about what is credible, not
  a neutral default. All of it is one checkbox away.
- **`VENUE_THRESHOLD = 5`.** See above.
- **`restore_case` output is offered as a `name` tag value.** It is a guess
  (`A-OK CAFE` → `A-Ok Cafe` is wrong). The source spelling is always shown beside
  it, which I think discharges the obligation, but an argument exists for never
  proposing `name` at all.
- **Category mappings in `config.TYPE_TO_OSM` / `SRV_TO_OSM`** are my reading of what
  a licensing category implies about a shopfront. `Banquet Facility` →
  `amenity=events_venue` and `Private Club` → `amenity=social_club` are the shakiest.
  `poi-categories` next door is a crosswalk project and may have better answers.

# Licensing — the code and the data are not under the same terms

**Code: MIT** (see `LICENSE`).
**Published data (`candidates.geojson`): ODbL 1.0**, because it is a derivative
database of OpenStreetMap.

## Why the data file is ODbL and not MIT

`candidates.geojson`, the file the explorer loads, is not a picture of a map. For
roughly 10,300 of its features it carries, taken directly from OpenStreetMap:

- the matched element's id (`node/7581385501`),
- its tag *values* — `name`, `addr:housenumber`, `addr:street`, `addr:postcode`,
  `amenity`, `shop`, `cuisine`, `website`, `opening_hours`, `brand`,
- and its coordinates, since a matched dot is drawn on the element a mapper would
  open rather than on the address point behind it.

A further 1,069 features — the "OSM, unlicensed" layer — are nothing *but* OSM data.

Under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) that makes the file
a **Derivative Database**, not a Produced Work. Produced Works (a rendered tile, a
screenshot) need only attribution; a derivative database carries the share-alike
condition. So the published file is offered under ODbL 1.0, and anyone
redistributing it or a database built from it must do the same.

The explorer *page* — HTML, CSS, JavaScript — is a Produced Work and stays MIT.

## Sources and required attribution

| source | licence | what is used |
|---|---|---|
| [DineSafe](https://open.toronto.ca/dataset/dinesafe/) and [BodySafe](https://open.toronto.ca/dataset/bodysafe/), City of Toronto | [Open Government Licence – Toronto](https://open.toronto.ca/open-data-license/) | establishment names, addresses, postcodes, phone numbers, inspection dates and categories |
| [Address Points](https://open.toronto.ca/dataset/address-points-municipal-toronto-one-address-repository/), City of Toronto | Open Government Licence – Toronto | the coordinates a candidate is anchored to |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | ODbL 1.0 | existing POIs, their tags and positions, and the basemap tiles |

Both are on the OSM Foundation's compatible list — OGL–Toronto is tracked as
`green-lwg` in `ontario-address-changes/LICENSING.md` — so the two combine without
a waiver, and data from these feeds may be used in OpenStreetMap.

The required credit line, carried in the page footer:

> Contains information made available under the Open Government Licence – Toronto.
> Contains OpenStreetMap data, © OpenStreetMap contributors, ODbL 1.0.

## The concern that is not a licensing one

This site lists thousands of businesses that OpenStreetMap does not have, each with
a one-click link into an editor. That is a convenient shape for a bulk import, and a
bulk import is exactly what it must not be used for.

Nothing here has been checked against the ground. The matching is automated, the
categories are inferred from a licensing category rather than a shopfront, the names
are reconstructed from capitals, and roughly a third of the coordinates come from a
health-unit geocode rather than a surveyed point. It is a queue of places worth
looking at.

Anyone using it to edit OpenStreetMap should read the
[Import Guidelines](https://wiki.openstreetmap.org/wiki/Import/Guidelines) and the
[Automated Edits code of conduct](https://wiki.openstreetmap.org/wiki/Automated_Edits_code_of_conduct)
first. Nothing here has been through an import proposal, and no import has been
proposed.

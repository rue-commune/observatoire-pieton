# Data generator (Nantes Métropole)

`nantes.py` rebuilds `assets/villes/nantes/data.json` from open data. Hugo
never sees this directory; only the generated file is inlined into the
site. Each run that writes the site's `data.json` also archives a
snapshot and rebuilds the progress history (see [History](#history)).

## Updating the data

[DATA-UPDATE.md](../../DATA-UPDATE.md) at the repository root is the
monthly procedure, with what to look for and what the warnings mean.
In short:

```sh
./docker/docker-manage.sh data            # download, compute, write
git show HEAD:assets/villes/nantes/data.json > /tmp/old.json
python3 scripts/data/compare.py /tmp/old.json assets/villes/nantes/data.json
python3 scripts/data/compare.py archives/nantes/<previous>.json \
    archives/nantes/<today>.json
./docker/docker-manage.sh test
```

`compare.py` and `history.py` need only Python 3's standard library, so
they run on the host as well as in the container
(`./docker/docker-manage.sh sh`). Comparing two data.json files matches
crossings by exact position; comparing two snapshots matches them by id
and checks each id's position (see [History](#history)).
Then review the comparison (headline and per-commune figures, places to
remove, status changes, id warnings) and commit the data update on its
own, with `nantes-order.json`, the new snapshot, `history.json`, and
`config.json` if its source dates changed.

If a crossing id moved and could not be matched by position, the script
writes everything, prints a banner and exits with status 3; so do
`compare.py` on snapshots and `history.py` (for the latest snapshot).
Look at those crossings in the source data before committing.

To discard an update, restore the committed files and delete the new
untracked ones, its snapshot included (DATA-UPDATE.md has the
commands): rows follow the latest snapshot, and a leftover one that
disagrees with `nantes-order.json` stops the next run before it writes
anything.

`data` takes the script's own options after it (`--help` lists them):
`--offline` reuses the last downloads in `.cache/data/nantes/` (git-ignored),
`--out` writes elsewhere, `--no-config` leaves `config.json` alone, and
`--debug` writes which spaces each crossing picked up, by dataset id.

## Inputs

- The six Nantes Métropole datasets listed in `config.json` `sources`,
  from the Opendatasoft API (`exports/geojson`). A download is rejected
  if its feature count differs from the dataset's metadata.
- The OpenStreetMap road network, from Overpass. The main instance is
  often saturated, so mirrors are tried in turn.
- `nantes-communes.geojson`: commune contours (france-geojson, after IGN),
  simplified. Communes rarely change, so the file is kept here rather than
  fetched; a commune missing from it stops the run.

The script updates the `date` of a source in `config.json` only where
one is already present (today, OpenStreetMap). It edits the date string
in place and never re-serialises the file.

## Method

`config.json` `methode` describes it for readers. The original generator
was not available, so this one was rebuilt from that text and the
published `data.json` of 5 November 2026, and calibrated against it. On
the same crossings (matched by position), 99.5 % get the same status and
the headline rate is identical (86.0 %). Details the text leaves out,
settled by that calibration:

- Work in Lambert-93. A crossing's position is the centroid of its line;
  its direction and length come from its two farthest vertices.
- The zone is cut into quadrants at the crossing's line and midpoint.
  Upstream are two diagonal quadrants (traffic keeps right), or, on a
  one-way street without contraflow cycling, both quadrants on the side
  traffic comes from. The 3 m crossing band itself is upstream on both
  sides. A crossing over a divided road (one-way carriageways in opposite
  directions) follows the two-way rule; the original generator applied
  the one-way rule of the nearest carriageway, and this departs from it
  on about 1,000 crossings and 34 statuses. A space is upstream if it
  overlaps the upstream part by 0.5 m²,
  otherwise downstream if it overlaps the zone by 0.5 m².
- Places are counted on the side the space is assigned to. A free strip
  has (overlap ÷ 2.2 m) ÷ (5.5 or 2.5 m) places, rounded up; a space with
  several places counts them in proportion to its overlap.
- A free strip running within 45° of the crossing's direction belongs to
  the cross street and is ignored.
- An aire de livraison with no length is taken as 6 m per place.
- Reserved spaces count `nombre_place` places, or 1 when it is empty.
- Places to remove, per commune and quartier, count each space once:
  the places it has within the union of the zones (or of their upstream
  parts, for the law) of the crossings it affects there.
- Street names come from the nearest OSM road running along the street
  (named roads preferred). Service roads and pedestrian areas are
  ignored. Junctions are searched within 200 m; within 18 m the crossing
  is "à l'angle de" the street running most squarely across.

## Row order

Permalinks (`#passage-N`) and the ids in exported files are row indices,
so rows keep their published order. `nantes-order.json` lists the
crossing ids in that order; it is rewritten whenever the script writes
the site's `data.json`, and is committed with it. New crossings go at
the end; a deleted crossing still shifts the rows after it. Without the
file (the first run), the order is recovered from the published
`data.json` by matching positions.

## History

Every run that writes the site's `data.json` also writes
`archives/nantes/YYYY-MM-DD.json` (the run's date; a second run on the
same day replaces it, and is linked to the previous date as the first
was). A snapshot holds, in `data.json` row order, each
crossing's position, commune, quartier and status masks, with its
source id (`gid`), plus the places to remove, the source dates and the
method version. One crossing per line keeps git diffs readable. The
archive is committed but never shipped to the browser: it is outside
`assets/` and outside Hugo's `data/` directory, which Hugo would load
on every build.

`history.py` then rebuilds `assets/villes/nantes/history.json` from the
whole archive (the generator logs only the latest link's anomalies;
`python3 scripts/data/history.py` alone logs every link's): status
counts per date for the metropolis and per commune, places to remove
per date, and, for each crossing whose status
changed since the first snapshot, the snapshot where its current status
began (and what it was before). Never edit it by hand; the test gate
checks that it matches the archive. Run `python3 scripts/data/history.py`
to rebuild it alone.

Statuses are the app's full status (all categories but bicycles).

Crossings are followed from one snapshot to the next by id, but an id is
trusted only if it is still within 3 m of where it was. Ids that moved,
new ids and vanished ids are then matched one to one by position (nearest
first, within 3 m), which repairs renumbered or swapped ids; each repair
is logged as a `WARNING`. An id that moved where no earlier crossing lay
is logged as `WARNING!!`: its history restarts, though it keeps its row
so that the rows after it don't shift. Ids must be unique in the source;
the generator stops before writing anything if they are not.

Rows keep the order of the latest snapshot (its ids are in `data.json`
row order; `nantes-order.json` serves only before the first snapshot).
The generator links the crossings to that snapshot before ordering them,
so repaired crossings keep their row (and permalink).

`METHODE` in `nantes.py` is the method version. Bump it whenever a change
to the rules changes statuses: a status change between snapshots of
different versions is recorded as a change of method, not of the street.

## Tests

`test_nantes.py` checks the geometric rules on synthetic cases, and
`test_history.py` the snapshots, id matching and history. The test
gate (`scripts/test.sh`, also run by CI) runs them, and checks the code
with black (79 columns) and flake8.

# Monthly data update

Do this **once a month**, around mid-month. Nantes Métropole updates its
parking datasets monthly or irregularly; the crossings dataset changes
less often. Every update adds one reading to the progress history, so a
skipped month is a gap that can never be filled in afterwards: the open
data has no history of its own.

Expect about half an hour, most of it waiting for downloads.

## What an update produces

One run of the generator writes, and the update commits together:

| File | What it is |
| --- | --- |
| `assets/villes/nantes/data.json` | The data the map shows. Replaced. |
| `archives/nantes/YYYY-MM-DD.json` | This month's snapshot: every crossing's id, position and status. Added; old ones are never edited. |
| `assets/villes/nantes/history.json` | Progress over time, rebuilt from all snapshots. |
| `scripts/data/nantes-order.json` | Crossing ids in row order, which keeps permalinks stable. |
| `assets/villes/nantes/config.json` | Only if source dates changed. |

The snapshots are the record of progress. They are committed for
traceability and never shipped to the browser.

## Steps

All commands run from the repository root, on the host; the generator
itself runs in Docker.

1. **Start clean.** Be on an up-to-date branch with no uncommitted
   changes under `assets/villes/`, `archives/` or `scripts/data/`.

2. **Run the generator.**

   ```sh
   ./docker/docker-manage.sh data
   ```

   It downloads the six Nantes Métropole datasets and OpenStreetMap
   (Overpass mirrors are tried in turn; a busy server can take several
   minutes or fail, in which case try again later), then computes and
   writes the files above. Read the end of its output:

   - exit status **0**: no problem with crossing ids;
   - exit status **3** and a `!!!!` banner: every file was written, but a
     crossing id needs a look (see [Warnings](#warnings)) before you
     commit;
   - it stops with an error and writes nothing: duplicate ids in the
     source, or a snapshot left over from an abandoned update (see
     [Abandoning an update](#abandoning-an-update)).

3. **Compare with last month.** Both commands run on the host (standard
   library only):

   ```sh
   git show HEAD:assets/villes/nantes/data.json > /tmp/old.json
   python3 scripts/data/compare.py /tmp/old.json assets/villes/nantes/data.json
   ls archives/nantes/          # the last two are last month and today
   python3 scripts/data/compare.py archives/nantes/<last month>.json \
       archives/nantes/<today>.json --examples 5
   ```

   On the very first update there is no earlier snapshot: skip the
   second command. Look for:

   - the headline rate and per-commune rates (`<--` marks a change of
     5 points or more in a commune): plausible for one month?
   - status transitions: `ko -> ok` is progress, `ok -> ko` a regression.
     A few dozen either way is normal; hundreds suggest a data clean-up
     or a change in a source rather than work in the street. Check a few
     examples on the map or in Street View.
   - places to remove: should drift slowly.
   - id warnings (see below). On a `WARNING!!` month the snapshot
     comparison also exits with status 3; that is expected.

4. **Check the source texts.** If Nantes Métropole changed the
   description of a dataset (its title, licence or what it covers),
   update the texts in `assets/villes/nantes/config.json` by hand; the
   generator only updates the dates.

5. **Run the test gate.**

   ```sh
   ./docker/docker-manage.sh test
   ```

   It also checks that `history.json` matches the archive.

6. **Look at the site** if the figures moved noticeably:
   `./docker/docker-manage.sh serve`, then http://localhost:1313/.

7. **Commit the update on its own**, with nothing else in the commit
   (see GIT.md for message style; an agent asks before committing, as
   GIT.md requires):

   ```sh
   git add assets/villes/nantes/data.json assets/villes/nantes/history.json \
       assets/villes/nantes/config.json archives/nantes/ \
       scripts/data/nantes-order.json
   git commit
   ```

   Say in the message what moved: headline rate, notable communes,
   number of status changes, and any id warnings and what you concluded.

## Warnings

Crossings are followed from month to month by their id in the source
data, and each id is checked against its position.

- `WARNING: id … is new; linked by position to former id …` or
  `… moved away; linked by position …`: Nantes renumbered or swapped
  ids. The crossing was recognised by its position (within 3 m), keeps
  its history and its permalink. Nothing to do unless there are many,
  which would mean a large renumbering worth a sentence in the commit
  message.
- `WARNING!! id … moved N m … its history restarts`: an id now points
  to a place where no crossing was before. Either the crossing was
  redrawn far away (a correction), or the id was reused for another
  crossing. Look at both positions on the map. The crossing usually
  keeps its row (so other permalinks don't shift; if another crossing
  now lies at its old place, that one takes the row and this one goes
  to the end), but its history starts again from this month. If it
  looks like a mistake in the source, consider reporting it to Nantes
  Métropole. Either way, note it in the commit message; the warning
  will not stop future updates.
- `N crossings returned to their status of two updates ago`: statuses
  that flipped and flipped back, usually noise in the source data.
  Worth a glance if the number is large.

## Abandoning an update

If the result looks wrong and you don't want to commit it, put back
the committed files **and delete the new, uncommitted ones** (the new
snapshot; on the very first update also `history.json` and
`nantes-order.json`). This works whether or not you had staged them:

```sh
git reset -q -- assets/villes/nantes archives scripts/data
git restore -- assets/villes/nantes
git clean -n -- assets/villes/nantes archives scripts/data  # preview
git clean -f -- assets/villes/nantes archives scripts/data
```

`git clean` deletes untracked files in those directories, which is
why step 1 asks you to start with nothing uncommitted there; check the
preview. A snapshot left behind makes the next run stop, because the
row order would no longer match the latest snapshot.

Running the generator twice on the same day is fine: the second run
replaces that day's snapshot and gives the same rows.

## If the method changes

If someone changes a rule in `scripts/data/nantes.py` that changes
crossings' statuses, they must bump `METHODE` there. Status changes
between snapshots of different method versions are then recorded as a
change of method, not progress in the street. Never edit or regenerate
old snapshots.

## More detail

`scripts/data/README.md` describes the generator's method, the snapshot
format, how crossings are matched, and the script options.

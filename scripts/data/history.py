#!/usr/bin/env python3
"""Snapshot archive and the progress history built from it.

Each data update also writes a snapshot of every crossing's status to
archives/nantes/YYYY-MM-DD.json, committed with data.json, so the
history can be traced and rebuilt. history.json is derived from the
whole archive and is never edited by hand. See scripts/data/README.md.

Standard library only, so it runs on the host as well as in Docker.
"""

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "archives" / "nantes"
HISTORY = ROOT / "assets" / "villes" / "nantes" / "history.json"

# Two crossings this close are taken as the same one. Positions are
# rounded to 1e-6 degrees (about 0.1 m), so a crossing whose drawing
# is untouched never moves.
MATCH_TOL = 3.0
# A crossing that keeps its id but moves more than this is reported.
SHIFT_NOTE = 0.5

KO, MID, OK = 0, 1, 2
NEW, METHOD = -1, -2
FULL = 15  # all categories but bicycles, like the app's full status

SNAPSHOT_FIELDS = [
    "lat",
    "lon",
    "commune",
    "quartier",
    "mask_amont",
    "mask_aval",
    "gid",
]
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def status(up, down):
    return KO if up & FULL else MID if down & FULL else OK


def compact(v):
    # history.json may be inlined into a <script> one day: never a raw "<"
    s = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c")


# ------------------------------------------------------------ snapshots


def snapshot(data, gids, methode, sources):
    """A snapshot of a data.json: rows in the same order, reduced to
    position, place and status masks, plus the source crossing id."""
    if len(gids) != len(data["rows"]):
        raise ValueError("one gid per row is needed")
    return {
        "generated": data["generated"],
        "methode": methode,
        "sources": dict(sorted(sources.items())),
        "communes": data["communes"],
        "quartiers": data["quartiers"],
        "removal": data["removal"],
        "fields": SNAPSHOT_FIELDS,
        "rows": [r[:6] + [g] for r, g in zip(data["rows"], gids)],
    }


def dump_snapshot(snap):
    """One crossing per line, so git stores and shows an update as the
    lines that changed."""
    head = [
        f"{json.dumps(k)}:{compact(v)}" for k, v in snap.items() if k != "rows"
    ]
    rows = ",\n".join(compact(r) for r in snap["rows"])
    return "{" + ",\n".join(head) + ',\n"rows":[\n' + rows + "\n]}\n"


def check_snapshot(snap, name):
    """Raise ValueError unless snap is a well-formed snapshot."""
    for k in ("generated", "methode", "communes", "removal", "rows"):
        if snap.get(k) is None:
            raise ValueError(f"{name}: missing {k!r}")
    if snap.get("fields") != SNAPSHOT_FIELDS:
        raise ValueError(f"{name}: unexpected fields {snap.get('fields')}")
    if not DATE_RE.fullmatch(str(snap["generated"])):
        raise ValueError(f"{name}: bad date {snap['generated']!r}")
    if not isinstance(snap["methode"], int) or snap["methode"] < 1:
        raise ValueError(f"{name}: bad methode {snap['methode']!r}")
    gids = set()
    for i, r in enumerate(snap["rows"]):
        if len(r) != len(SNAPSHOT_FIELDS) or not isinstance(r[6], str):
            raise ValueError(f"{name}: malformed row {i}")
        if r[6] in gids:
            raise ValueError(f"{name}: duplicate gid {r[6]!r}")
        gids.add(r[6])


def load_archive(directory=ARCHIVE):
    """All snapshots, oldest first."""
    out = []
    for p in sorted(Path(directory).glob("*.json")):
        if not DATE_RE.fullmatch(p.stem):
            raise ValueError(f"{p}: not named YYYY-MM-DD.json")
        snap = json.loads(p.read_text(encoding="utf-8"))
        check_snapshot(snap, p.name)
        if snap["generated"] != p.stem:
            raise ValueError(f"{p}: generated {snap['generated']}")
        out.append(snap)
    return out


# ---------------------------------------------------------------- links


def triples(snap):
    return [(r[6], r[0], r[1]) for r in snap["rows"]]


def _xy(lat, lon):
    # Local equirectangular metres: exact enough over a few metres.
    k = 6371008.8 * math.pi / 180
    return lon * k * math.cos(math.radians(lat)), lat * k


def distance(a, b):
    (x0, y0), (x1, y1) = _xy(*a), _xy(*b)
    return math.hypot(x1 - x0, y1 - y0)


class Link:
    """Which crossing of the new snapshot continues which of the old.

    pairs: new index -> old index. moved: (gid, new index, old index,
    metres) for ids found at both dates more than MATCH_TOL apart.
    repaired: (new index, old index) pairs made by position between
    crossings whose ids differ. unrepaired: the moved entries whose new
    crossing found no old one at its position, so it starts a new
    history. shifted: ids that moved between SHIFT_NOTE and MATCH_TOL
    (redrawn, still linked). new, gone: unlinked indices."""

    def __init__(self):
        self.pairs = {}
        self.moved = []
        self.repaired = []
        self.unrepaired = []
        self.shifted = 0
        self.new = []
        self.gone = []

    @property
    def hard(self):
        return bool(self.unrepaired)


def link(old, new, tol=MATCH_TOL):
    """Link two lists of (gid, lat, lon), ids unique within each.

    An id found at both dates links its crossings if they lie within
    tol. Everything else (new ids, vanished ids, and ids that moved) is
    then matched one to one by position, nearest pairs first, within
    tol: this repairs renumbered or swapped ids."""
    lk = Link()
    old_by_gid = {g: i for i, (g, _, _) in enumerate(old)}
    loose_new = []
    for j, (g, lat, lon) in enumerate(new):
        i = old_by_gid.get(g)
        if i is None:
            loose_new.append(j)
            continue
        d = distance(old[i][1:], (lat, lon))
        if d <= tol:
            lk.pairs[j] = i
            lk.shifted += d > SHIFT_NOTE
        else:
            lk.moved.append((g, j, i, d))
            loose_new.append(j)
    linked_old = set(lk.pairs.values())
    loose_old = [i for i in range(len(old)) if i not in linked_old]

    grid = defaultdict(list)
    for i in loose_old:
        x, y = _xy(*old[i][1:])
        grid[(int(x // tol), int(y // tol))].append(i)
    candidates = []
    for j in loose_new:
        x, y = _xy(*new[j][1:])
        cx, cy = int(x // tol), int(y // tol)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i in grid.get((cx + dx, cy + dy), ()):
                    d = distance(old[i][1:], new[j][1:])
                    if d <= tol:
                        candidates.append((d, j, i))
    used = set()
    for d, j, i in sorted(candidates):
        if j in lk.pairs or i in used:
            continue
        lk.pairs[j] = i
        used.add(i)
        lk.repaired.append((j, i))
    lk.unrepaired = [m for m in lk.moved if m[1] not in lk.pairs]
    lk.new = [j for j in loose_new if j not in lk.pairs]
    lk.gone = [i for i in loose_old if i not in used]
    return lk


def describe(lk, old, new, label):
    """Log a link's figures and anomalies; return True if any is hard."""
    by_id = len(lk.pairs) - len(lk.repaired)
    log(
        f"  {label}: {by_id} linked by id, {len(lk.repaired)} by position,"
        f" {len(lk.new)} new, {len(lk.gone)} gone"
        + (f", {lk.shifted} redrawn in place" if lk.shifted else "")
    )
    moved_new = {m[1] for m in lk.moved}
    for j, i in lk.repaired:
        g, d = new[j][0], distance(old[i][1:], new[j][1:])
        why = "moved away" if j in moved_new else "is new"
        log(
            f"  WARNING: id {g} {why}; linked by position to former id"
            f" {old[i][0]} ({d:.1f} m)"
        )
    for g, j, i, d in lk.unrepaired:
        log(
            f"  WARNING!! id {g} moved {d:.0f} m (from {old[i][1]},"
            f"{old[i][2]} to {new[j][1]},{new[j][2]}) and no earlier"
            " crossing lies at its new position: its history restarts."
            " Check the source data."
        )
    return lk.hard


# -------------------------------------------------------------- history


def fold(s):
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def build(snaps, links=None):
    """history.json from snapshots (oldest first). links[k] links
    snapshot k to k - 1 (links[0] is unused); computed if not given."""
    if links is None:
        links = [None] + [
            link(triples(a), triples(b)) for a, b in zip(snaps, snaps[1:])
        ]
    sts = [[status(r[4], r[5]) for r in s["rows"]] for s in snaps]
    last = len(snaps) - 1

    # Where each current crossing's status run began, unless at the
    # first snapshot: walk its links back until the status differs.
    changes = []
    for row, s in enumerate(sts[last]):
        cur, k = row, last
        while k > 0:
            prev = links[k].pairs.get(cur)
            if prev is None:
                changes.append([row, k, NEW])
                break
            if sts[k - 1][prev] != s:
                same = snaps[k]["methode"] == snaps[k - 1]["methode"]
                changes.append([row, k, sts[k - 1][prev] if same else METHOD])
                break
            cur, k = prev, k - 1

    names = sorted({c for s in snaps for c in s["communes"]}, key=fold)
    by_com = {c: [] for c in names}
    total, removal = [], []
    for s, st in zip(snaps, sts):
        counts = defaultdict(lambda: [0, 0, 0])
        for r, x in zip(s["rows"], st):
            counts[s["communes"][r[2]]][x] += 1
        for c in names:
            by_com[c].append(counts[c] if c in counts else None)
        total.append([sum(v[x] for v in counts.values()) for x in range(3)])
        rem = {}
        for per in s["removal"]["c"].values():
            for cat, (law, reco) in per.items():
                t = rem.setdefault(cat, [0, 0])
                t[0] += law
                t[1] += reco
        removal.append(dict(sorted(rem.items(), key=lambda kv: int(kv[0]))))

    return {
        "generated": snaps[last]["generated"],
        "fields": {
            "series": "[non conformes, conformes à la loi seulement,"
            " conformes à la recommandation] par relevé",
            "removal": "{catégorie: [places à supprimer (loi),"
            " (recommandation)]} par relevé",
            "changes": "[ligne de data.json, relevé où commence le statut"
            " actuel, statut précédent (0 non conforme, 1 loi seulement,"
            " 2 recommandation, -1 passage nouveau, -2 changement de"
            " méthode)] ; ligne absente : statut inchangé depuis le"
            " premier relevé",
        },
        "dates": [s["generated"] for s in snaps],
        "methodes": [s["methode"] for s in snaps],
        "series": {"total": total, "communes": by_com},
        "removal": removal,
        "changes": changes,
    }


def flapping(snaps, links):
    """Crossings whose status changed at the last snapshot back to what
    it was two snapshots ago: likely noise in the source data."""
    if len(snaps) < 3:
        return 0
    sts = [[status(r[4], r[5]) for r in s["rows"]] for s in snaps[-3:]]
    n = 0
    for j, s in enumerate(sts[2]):
        i = links[-1].pairs.get(j)
        h = links[-2].pairs.get(i) if i is not None else None
        n += h is not None and sts[1][i] != s and sts[0][h] == s
    return n


def rebuild(directory=ARCHIVE, out=HISTORY, report_all=True):
    """Rebuild out from the archive, logging the anomalies of every link
    (or only the latest one). Returns (history, hard), where hard says
    the latest link has an unrepaired id, or None if the archive is
    empty."""
    snaps = load_archive(directory)
    if not snaps:
        log(f"No snapshots in {directory}")
        return None
    links = [None]
    hard = False
    for a, b in zip(snaps, snaps[1:]):
        lk = link(triples(a), triples(b))
        links.append(lk)
        hard = lk.hard
        if report_all or b is snaps[-1]:
            label = f"{a['generated']} -> {b['generated']}"
            describe(lk, triples(a), triples(b), label)
    hist = build(snaps, links)
    flips = flapping(snaps, links)
    if flips:
        log(f"  {flips} crossings returned to their status of two updates ago")
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(compact(hist) + "\n", encoding="utf-8")
    tmp.replace(out)
    log(f"Wrote {out} ({len(snaps)} snapshots)")
    return hist, hard


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--archive", type=Path, default=ARCHIVE)
    ap.add_argument("--out", type=Path, default=HISTORY)
    a = ap.parse_args(argv)
    r = rebuild(a.archive, a.out)
    return 3 if r and r[1] else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Compare two data.json files, to review a data update before committing.

Crossings are matched by coordinates, since row indices may change.
Prints headline figures for each file, per-commune changes, and for
matched crossings how many changed status, road type or street name.
"""

import argparse
import json
from collections import Counter


def status(row):
    return "ko" if row[4] & 15 else "mid" if row[5] & 15 else "ok"


def summary(rows):
    s = Counter(status(r) for r in rows)
    n = len(rows) or 1
    return s, (s["ok"] + s["mid"]) / n * 100


def street_names(d, i):
    st = d.get("st")
    if not st:
        return None
    names = d.get("streets", [])
    return tuple(names[k] if k > -1 else None for k in st[i])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument(
        "--examples",
        type=int,
        default=0,
        help="list this many changed crossings of each kind",
    )
    a = ap.parse_args(argv)
    old, new = (json.load(open(p, encoding="utf-8")) for p in (a.old, a.new))

    for name, d in (("old", old), ("new", new)):
        s, law = summary(d["rows"])
        print(
            f"{name}: generated {d['generated']},"
            f" {len(d['rows'])} crossings,"
            f" {law:.1f} % lawful (ko {s['ko']}, mid {s['mid']},"
            f" ok {s['ok']})"
        )

    print("\nPer commune: crossings, % lawful (old -> new)")
    for c in sorted(set(old["communes"]) | set(new["communes"])):
        line = []
        for d in (old, new):
            ci = d["communes"].index(c) if c in d["communes"] else None
            rows = [r for r in d["rows"] if r[2] == ci]
            line.append((len(rows), summary(rows)[1]))
        (n0, l0), (n1, l1) = line
        flag = "  <--" if abs(l1 - l0) >= 5 else ""
        print(f"  {c:28} {n0:5} {l0:5.1f} % -> {n1:5} {l1:5.1f} %{flag}")

    print("\nPlaces to remove, law / recommendation (old -> new)")
    cats = {1: "voitures", 2: "livraisons", 4: "deux-roues", 8: "GIG-GIC"}
    tot = [{}, {}]
    for t, d in zip(tot, (old, new)):
        for per in d["removal"]["c"].values():
            for k, (law, reco) in per.items():
                x = t.setdefault(int(k), [0, 0])
                x[0] += law
                x[1] += reco
    for k, name in cats.items():
        (l0, r0), (l1, r1) = (t.get(k, [0, 0]) for t in tot)
        print(f"  {name:12} {l0:6} / {r0:6} -> {l1:6} / {r1:6}")

    by_pos = {}
    for i, r in enumerate(old["rows"]):
        by_pos.setdefault((r[0], r[1]), i)
    pairs = [
        (by_pos[(r[0], r[1])], j)
        for j, r in enumerate(new["rows"])
        if (r[0], r[1]) in by_pos
    ]
    print(
        f"\nMatched by position: {len(pairs)} of {len(new['rows'])} new"
        f" crossings ({len(old['rows']) - len(pairs)} old ones unmatched)"
    )
    trans, kinds = Counter(), {}
    for i, j in pairs:
        ro, rn = old["rows"][i], new["rows"][j]
        trans[(status(ro), status(rn))] += 1
        checks = {
            "status": status(ro) != status(rn),
            "road": ro[9] != rn[9],
            "upstream mask": ro[4] != rn[4],
            "downstream mask": ro[5] != rn[5],
            "places": sorted(map(tuple, ro[6])) != sorted(map(tuple, rn[6])),
            "street": street_names(old, i) != street_names(new, j),
        }
        for k, changed in checks.items():
            if changed:
                kinds.setdefault(k, []).append((i, j))
    print("Status transitions (old -> new):")
    for (s0, s1), n in sorted(trans.items()):
        print(f"  {s0:>3} -> {s1:<3} {n}")
    print("Matched crossings that differ:")
    for k, v in kinds.items():
        print(f"  {k:16} {len(v)} ({len(v) / max(1, len(pairs)) * 100:.1f} %)")
        for i, j in v[: a.examples]:
            ro, rn = old["rows"][i], new["rows"][j]
            print(
                f"     {ro[0]},{ro[1]} old {ro[4:7]} road {ro[9]}"
                f" {street_names(old, i)}"
            )
            print(
                f"     {' ' * len(f'{ro[0]},{ro[1]}')} new {rn[4:7]}"
                f" road {rn[9]} {street_names(new, j)}"
            )


if __name__ == "__main__":
    main()

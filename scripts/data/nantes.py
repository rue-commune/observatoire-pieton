#!/usr/bin/env python3
"""Generate assets/villes/nantes/data.json from open data.

Reads Nantes Métropole's crossings and parking datasets and the
OpenStreetMap road network, applies the method described in config.json
("methode"), and writes the data file the app inlines. Run it through
`./docker/docker-manage.sh data`; see scripts/data/README.md.
"""

import argparse
import datetime
import json
import math
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from pyproj import Transformer
from shapely import STRtree
from shapely.affinity import affine_transform
from shapely.geometry import LineString, Point, box, shape
from shapely.ops import transform as shp_transform, unary_union

import history as H

ROOT = Path(__file__).resolve().parents[2]
VILLE = ROOT / "assets" / "villes" / "nantes"
COMMUNES_GEOJSON = Path(__file__).resolve().parent / "nantes-communes.geojson"
DEFAULT_CACHE = ROOT / ".cache" / "data" / "nantes"
# Crossing ids in published row order; updated with each data.json.
ORDER_FILE = Path(__file__).resolve().parent / "nantes-order.json"

API = "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/"
DS_CROSSINGS = "244400404_traversees-pietones-nantes-metropole"
DS_PAID = "244400404_stationnement-nantes-emplacements"
DS_FREE = "244400404_emplacements-gratuits-materialises-nantes-metropole"
DS_RESERVED = "244400404_emplacements-stationnement-reserves-nantes-metropole"
DS_DELIVERY = "244400404_aires-livraison-nantes-metropole"
DS_PMR = "244400404_emplacements-pmr-nantes-metropole"
DATASETS = [DS_CROSSINGS, DS_PAID, DS_FREE, DS_RESERVED, DS_DELIVERY, DS_PMR]

# The main Overpass instance is often saturated; mirrors serve the same
# data. Tried in order.
OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
# Roads that can carry a pedestrian crossing or name a junction. Footways,
# cycleways and paths are left out: they are not "the street".
HIGHWAYS = (
    "motorway|trunk|primary|secondary|tertiary|unclassified|"
    "residential|living_street|service|pedestrian|road|busway"
)
# Service roads (driveways, car park aisles) and pedestrian areas
# neither carry the street's name nor make a junction worth naming.
MINOR_HIGHWAYS = {"service", "pedestrian"}
HIGHWAY_RANK = {
    h: i
    for i, h in enumerate(
        "motorway trunk primary secondary tertiary unclassified residential "
        "living_street road busway pedestrian service".split()
    )
}
for _h in list(HIGHWAY_RANK):
    HIGHWAY_RANK[_h + "_link"] = HIGHWAY_RANK[_h]
# Bump whenever a rule changes a crossing's status, so the history tells
# a change of method from a change in the street. Recorded in each
# snapshot (see history.py).
METHODE = 1

USER_AGENT = "observatoire-pieton-data/1.0 (+https://5metres.fr/)"

# Method parameters, as stated in config.json "methode".
DIST = 4.0  # zone length beyond the crossing, each side (law: 5 m)
HALF_CROSSING = 1.5  # crossings are taken as 3 m wide along the street
LAT = 2.5  # zone overhang beyond each end of the crossing
MIN_AREA = 0.5  # m² of overlap for a space to count
STRIP_WIDTH = 2.2  # width given to free spaces drawn as a kerb line
PLACE_LENGTH = {"Longitudinale": 5.5, "Epi ou Bataille": 2.5}
PMR_RADIUS = 2.5
# Length per place of an aire de livraison whose length is not given
DELIVERY_PLACE_LENGTH = 6.0
CORNER_DIST = 18.0  # junction closer than this: "à l'angle de"
JUNCTION_SEARCH = 200.0  # how far along the street to look for junctions
# A strip whose direction is closer to the crossing's than this belongs
# to the cross street at a junction.
CROSS_STREET_ANGLE = 45.0

CATS = {"voiture": 1, "livraison": 2, "moto": 4, "gig": 8, "velo": 16}
# Fixed order, so labels keep their indices from one update to the next.
LABELS = [
    "Gratuit, longitudinal",
    "Place PMR (GIG-GIC)",
    "Gratuit, épi ou bataille",
    "Réservé (autre)",
    "Payant, zone jaune",
    "Arrêt minute",
    "Aire de livraison",
    "Deux-roues motorisés",
    "Payant, zone rouge",
    "Taxis",
    "Ambulances",
]
TYPES = ["Résine", "Blanc", "Autre", "Clous"]
RESERVED = {  # typereservation -> (category, label)
    "Moto": (4, "Deux-roues motorisés"),
    "Arrêt 15 minutes": (1, "Arrêt minute"),
    "Taxi": (1, "Taxis"),
    "Ambulance / VSL": (1, "Ambulances"),
}
ROAD_TWO_WAY, ROAD_ONE_WAY_CONTRAFLOW, ROAD_ONE_WAY = 0, 1, 2
SIDE_UP, SIDE_DOWN = 1, 2

TO_L93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
TO_WGS = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- download


def http_get(url, data=None, timeout=600, tries=3):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(
        url, data=body, headers={"User-Agent": USER_AGENT}
    )
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except OSError as e:
            if attempt == tries:
                raise
            log(f"  {url}: {e}; retrying")
            time.sleep(10 * attempt)


def save(path, data):
    """Write via a temporary file, so an interrupted run never leaves a
    truncated file behind."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def fetch(cache, offline, bbox):
    """Download the inputs into cache (unless offline) and return paths."""
    cache.mkdir(parents=True, exist_ok=True)
    paths = {}
    for ds in DATASETS:
        geo, meta = cache / f"{ds}.geojson", cache / f"{ds}.meta.json"
        if not offline:
            log(f"Downloading {ds}")
            raw_meta = http_get(API + ds)
            raw = http_get(API + ds + "/exports/geojson")
            # A short export would silently shrink the observatory.
            metas = json.loads(raw_meta)["metas"]["default"]
            expected = metas["records_count"]
            got = len(json.loads(raw)["features"])
            if got != expected:
                sys.exit(
                    f"{ds}: export has {got} features, "
                    f"metadata announces {expected}"
                )
            save(meta, raw_meta)
            save(geo, raw)
        paths[ds] = (geo, meta)
    osm = cache / "osm.json"
    if not offline:
        s, w, n, e = bbox
        query = (
            f'[out:json][timeout:300];way["highway"~"^({HIGHWAYS})'
            f'(_link)?$"]({s},{w},{n},{e});out body;>;out skel qt;'
        )
        for url in OVERPASS:
            log(f"Downloading OSM roads from {url}")
            try:
                raw = http_get(url, {"data": query}, tries=2)
                json.loads(raw)["osm3s"]  # reject error pages
            except (OSError, ValueError, KeyError) as e:
                log(f"  failed: {e}")
                continue
            save(osm, raw)
            break
        else:
            sys.exit("Every Overpass instance failed")
    paths["osm"] = osm
    for p in [osm] + [x for ds in DATASETS for x in paths[ds]]:
        if not p.exists():
            sys.exit(f"Missing {p}; run without --offline first")
    return paths


# ---------------------------------------------------------------- geometry


def to_l93(geom):
    return shp_transform(TO_L93.transform, geom)


class Frame:
    """Local frame of a crossing: origin at its centroid, x along the
    crossing (across the street), y along the street. Facing +y, +x is on
    the right."""

    def __init__(self, line):
        # Direction and length from the farthest pair of vertices, not
        # the end points: some crossings are drawn out and back (A-B-A).
        pts = list(line.coords)
        (x0, y0), (x1, y1) = max(
            ((p, q) for i, p in enumerate(pts) for q in pts[i + 1 :]),
            key=lambda pq: math.dist(*pq),
        )
        n = math.hypot(x1 - x0, y1 - y0) or 1.0
        self.ux, self.uy = (x1 - x0) / n, (y1 - y0) / n
        self.dx, self.dy = -self.uy, self.ux
        m = line.centroid
        self.mx, self.my = m.x, m.y
        self.length = n
        self.matrix = [
            self.ux,
            self.uy,
            self.dx,
            self.dy,
            -(self.ux * m.x + self.uy * m.y),
            -(self.dx * m.x + self.dy * m.y),
        ]

    def local(self, geom):
        return affine_transform(geom, self.matrix)

    def point(self, x, y):
        return (
            (x - self.mx) * self.ux + (y - self.my) * self.uy,
            (x - self.mx) * self.dx + (y - self.my) * self.dy,
        )

    def along_street(self, vx, vy):
        """Component of a direction vector along the street (+y)."""
        return vx * self.dx + vy * self.dy

    def regions(self, road, traffic_sign):
        """The zone and its upstream part, in the local frame.

        The zone is cut into quadrants at the crossing's centre line and
        midpoint. The crossing itself (|y| <= HALF_CROSSING) is upstream
        on both sides: a space on the crossing always counts."""
        s, t = self.length / 2 + LAT, HALF_CROSSING + DIST
        parts = [box(-s, -HALF_CROSSING, s, HALF_CROSSING)]
        for sx, sy in upstream_quadrants(road, traffic_sign):
            parts.append(
                box(
                    min(0, sx * s),
                    min(0, sy * t),
                    max(0, sx * s),
                    max(0, sy * t),
                )
            )
        return box(-s, -t, s, t), unary_union(parts)


def upstream_quadrants(road, traffic_sign):
    """Quadrants from which vehicles approach the crossing.

    Traffic keeps right, so on a two-way street (or a one-way street with
    contraflow cycling) vehicles heading +y use the +x half and arrive
    from -y, and those heading -y use the -x half and arrive from +y: the
    upstream quadrants are diagonal. On a one-way street they are the two
    on the side traffic comes from. traffic_sign is +1 when one-way
    traffic heads +y, -1 when it heads -y."""
    if road == ROAD_ONE_WAY:
        return {(-1, -traffic_sign), (1, -traffic_sign)}
    return {(1, -1), (-1, 1)}


# ---------------------------------------------------------------- inputs


def load_geojson(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))["features"]


def tidy_quartier(name):
    """Harmonise the dataset's separators: "A - B" -> "A – B",
    "A/B" -> "A / B"."""
    if not name:
        return None
    name = re.sub(r"\s+-\s+", " – ", name.strip())
    name = re.sub(r"\s*/\s*", " / ", name)
    return re.sub(r"\s+", " ", name)


class Space:
    """A parking feature: geometry in Lambert-93 and how to count it."""

    __slots__ = ("key", "cat", "label", "geom", "line", "per_place", "nb")

    def __init__(self, key, cat, label, geom, line=None, per_place=None, nb=1):
        self.key, self.cat, self.label = key, cat, label
        self.geom, self.line, self.per_place, self.nb = (
            geom,
            line,
            per_place,
            nb,
        )


def load_spaces(paths):
    spaces = []
    for f in load_geojson(paths[DS_PAID][0]):
        p, g = f["properties"], f["geometry"]
        if not g:
            continue
        label = (
            "Payant, zone rouge"
            if p.get("type_zone") == "Rouge"
            else "Payant, zone jaune"
        )
        spaces.append(
            Space(
                ("paid", p["space_id"]), 1, label, to_l93(shape(g)).buffer(0)
            )
        )
    for f in load_geojson(paths[DS_FREE][0]):
        p, g = f["properties"], f["geometry"]
        if not g:
            continue
        forme = p.get("forme") or "Longitudinale"
        label = (
            "Gratuit, épi ou bataille"
            if forme == "Epi ou Bataille"
            else "Gratuit, longitudinal"
        )
        line = to_l93(shape(g))
        spaces.append(
            Space(
                ("free", p["gid"]),
                1,
                label,
                line.buffer(STRIP_WIDTH / 2, cap_style="flat"),
                line=line,
                per_place=PLACE_LENGTH.get(forme, 5.5),
            )
        )
    for f in load_geojson(paths[DS_RESERVED][0]):
        p, g = f["properties"], f["geometry"]
        if not g:
            continue
        cat, label = RESERVED.get(
            p.get("typereservation"), (1, "Réservé (autre)")
        )
        spaces.append(
            Space(
                ("reserved", p["gid"]),
                cat,
                label,
                to_l93(shape(g)).buffer(0),
                nb=p.get("nombre_place") or 1,
            )
        )
    for f in load_geojson(paths[DS_DELIVERY][0]):
        p, g = f["properties"], f["geometry"]
        if not g:
            continue
        nb = p.get("nombre_place") or 1
        r = (p.get("longueur") or DELIVERY_PLACE_LENGTH * nb) / 2
        spaces.append(
            Space(
                ("delivery", p["gid"]),
                2,
                "Aire de livraison",
                to_l93(shape(g)).buffer(r),
                nb=nb,
            )
        )
    for f in load_geojson(paths[DS_PMR][0]):
        p, g = f["properties"], f["geometry"]
        if not g:
            continue
        spaces.append(
            Space(
                ("pmr", p["gid"]),
                8,
                "Place PMR (GIG-GIC)",
                to_l93(shape(g)).buffer(PMR_RADIUS),
            )
        )
    return spaces


# ---------------------------------------------------------------- OSM


def is_oneway(tags):
    v = tags.get("oneway")
    if v in ("yes", "true", "1"):
        return 1
    if v == "-1":
        return -1
    if v is None and tags.get("junction") in ("roundabout", "circular"):
        return 1
    if v is None and tags.get("highway") in ("motorway", "motorway_link"):
        return 1
    return 0


def has_contraflow(tags):
    """Whether OSM records contraflow cycling on a one-way street."""
    if tags.get("oneway:bicycle") == "no":
        return True
    for k in ("cycleway", "cycleway:left", "cycleway:right", "cycleway:both"):
        if (tags.get(k) or "").startswith("opposite"):
            return True
    return False


class Roads:
    def __init__(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.date = data["osm3s"]["timestamp_osm_base"][:10]
        nodes = {}
        for e in data["elements"]:
            if e["type"] == "node":
                nodes[e["id"]] = TO_L93.transform(e["lon"], e["lat"])
        self.ways, geoms = [], []
        self.node_ways = defaultdict(list)
        for e in data["elements"]:
            if e["type"] != "way":
                continue
            ids = [n for n in e["nodes"] if n in nodes]
            if len(ids) < 2 or e["tags"].get("highway") in MINOR_HIGHWAYS:
                continue
            i = len(self.ways)
            self.ways.append((e["tags"], ids))
            geoms.append(LineString([nodes[n] for n in ids]))
            for n in ids:
                self.node_ways[n].append(i)
        self.nodes, self.geoms = nodes, geoms
        self.tree = STRtree(geoms)

    def crossed_way(self, line, frame):
        """The road the crossing line crosses, as (way, direction along
        the street, named way, dual), or None.

        Candidates must pass near the crossing midpoint and run roughly
        along the street; the closest wins, intersecting ones first. The
        named way is the best named candidate, which gives the street its
        name when the best way is an unnamed slip road or carriageway.
        dual is true when the crossing cuts one-way ways running in
        opposite directions: the two carriageways of a divided road."""
        mid = Point(frame.mx, frame.my)
        best = named = None
        directions = set()
        for i in self.tree.query(mid.buffer(15.0)):
            g = self.geoms[i]
            d = g.distance(mid)
            # direction of the way where it passes nearest the crossing
            pos = g.project(mid)
            a = g.interpolate(max(0.0, pos - 2.0))
            b = g.interpolate(min(g.length, pos + 2.0))
            vx, vy = b.x - a.x, b.y - a.y
            n = math.hypot(vx, vy)
            if n == 0:
                continue
            along = abs(frame.along_street(vx, vy)) / n
            if along < math.cos(math.radians(50)):
                continue  # parallel to the crossing: not the crossed road
            score = (0 if g.intersects(line) else 1, d)
            ow = is_oneway(self.ways[i][0])
            if ow and score[0] == 0:
                directions.add(
                    1 if frame.along_street(vx, vy) * ow > 0 else -1
                )
            if best is None or score < best[0]:
                best = (score, i, frame.along_street(vx, vy) / n)
            if self.ways[i][0].get("name") and (
                named is None or score < named[0]
            ):
                named = (score, i)
        if best is None:
            return None
        return (
            best[1],
            best[2],
            named[1] if named else None,
            len(directions) == 2,
        )

    def junctions(self, way_index, frame):
        """Junctions of the named crossed street with other named streets,
        as (distance, y in the crossing frame, other name), within
        JUNCTION_SEARCH of the crossing."""
        name = self.ways[way_index][0].get("name")
        if not name:
            return []
        mid = Point(frame.mx, frame.my)
        near = self.tree.query(mid.buffer(JUNCTION_SEARCH))
        street = [i for i in near if self.ways[i][0].get("name") == name]
        found = {}
        for i in street:
            for n in self.ways[i][1]:
                if n in found:
                    continue
                x, y = self.nodes[n]
                d = math.hypot(x - frame.mx, y - frame.my)
                if d > JUNCTION_SEARCH:
                    continue
                other = self.cross_street(n, name, frame)
                if other:
                    found[n] = (d, frame.point(x, y)[1], other)
        return sorted(found.values())

    def cross_street(self, node, name, frame):
        """Name of the street meeting `name` at node, or None. Where
        several meet, the one running most squarely across the crossed
        street wins (rather than one continuing it under a new name)."""
        best = None
        x0, y0 = self.nodes[node]
        for j in self.node_ways[node]:
            tags, ids = self.ways[j]
            other = tags.get("name")
            if other in (name, None):
                continue
            k = ids.index(node)
            for m in (k - 1, k + 1):
                if 0 <= m < len(ids):
                    x1, y1 = self.nodes[ids[m]]
                    vx, vy = x1 - x0, y1 - y0
                    n = math.hypot(vx, vy) or 1.0
                    across = abs(frame.along_street(vx, vy)) / n
                    key = (
                        across,
                        HIGHWAY_RANK.get(tags.get("highway"), 99),
                        other,
                    )
                    if best is None or key < best:
                        best = key
        return best[2] if best else None


# ---------------------------------------------------------------- compute


def count_places(space, local_geom, local_line, zone, upstream):
    """(places, side) for a space near a crossing, or None when it does
    not count. Coordinates are in the crossing's local frame."""
    area = local_geom.intersection(zone).area
    if area < MIN_AREA:
        return None
    a_up = local_geom.intersection(upstream).area
    side = SIDE_UP if a_up >= MIN_AREA else SIDE_DOWN
    # The places counted are those on the side the space is assigned to.
    a_side = a_up if side == SIDE_UP else area - a_up
    if local_line is None:
        return places_in(space, a_side), side
    # A strip running across the street at a junction belongs to the
    # cross street. Judge its direction near the zone, from the longest
    # piece of its centre line there.
    near = local_line.intersection(zone.buffer(STRIP_WIDTH / 2))
    parts = [
        g
        for g in getattr(near, "geoms", [near])
        if g.geom_type == "LineString" and g.length > 0
    ]
    if parts:
        piece = max(parts, key=lambda g: g.length)
        (x0, y0), (x1, y1) = piece.coords[0], piece.coords[-1]
        if abs(y1 - y0) < abs(x1 - x0) * math.tan(
            math.radians(90 - CROSS_STREET_ANGLE)
        ):
            return None
    return places_in(space, a_side), side


def places_in(space, area):
    """Places of a space within `area` m² of it."""
    if space.line is not None:
        # Length of strip concerned, from the overlap: this still counts
        # a strip whose centre line runs just outside the zone.
        length = area / STRIP_WIDTH
        return max(1, math.ceil(length / space.per_place - 1e-9))
    if space.nb > 1:
        # A multi-place space counts in proportion to its overlap.
        return max(1, math.ceil(space.nb * area / space.geom.area - 1e-9))
    return space.nb


def compute(crossings, spaces, roads):
    tree = STRtree([s.geom for s in spaces])
    communes = sorted({c["commune"] for c in crossings}, key=fold)
    com_index = {c: i for i, c in enumerate(communes)}
    quartiers, q_index = [], {}
    streets, s_index = [], {}

    def street_id(name):
        if not name:
            return -1
        if name not in s_index:
            s_index[name] = len(streets)
            streets.append(name)
        return s_index[name]

    rows, st, hits = [], [], []
    for n, c in enumerate(crossings):
        if n % 2000 == 0:
            log(f"  crossing {n}/{len(crossings)}")
        line, frame = c["line"], Frame(c["line"])
        ci = com_index[c["commune"]]
        qi = -1
        if c["quartier"]:
            k = (c["quartier"], ci)
            if k not in q_index:
                q_index[k] = len(quartiers)
                quartiers.append({"n": c["quartier"], "c": ci})
            qi = q_index[k]

        # street, direction and junctions from OSM
        road, traffic = ROAD_TWO_WAY, 1
        sid = angle = e1 = e2 = -1
        found = roads.crossed_way(line, frame)
        if found:
            wi, along, wn, dual = found
            tags = roads.ways[wi][0]
            ow = is_oneway(tags)
            # A divided road has traffic both ways: keep the two-way rule.
            if ow and not dual:
                road = (
                    ROAD_ONE_WAY_CONTRAFLOW
                    if has_contraflow(tags)
                    else ROAD_ONE_WAY
                )
                traffic = 1 if along * ow > 0 else -1
            if wn is not None:
                wi = wn
            sid = street_id(roads.ways[wi][0].get("name"))
            js = roads.junctions(wi, frame)
            if js and js[0][0] <= CORNER_DIST:
                angle = street_id(js[0][2])
            else:
                before = next((j for j in js if j[1] < 0), None)
                after = next((j for j in js if j[1] > 0), None)
                if before and after and before[2] != after[2]:
                    e1, e2 = street_id(before[2]), street_id(after[2])

        zone, upstream = frame.regions(road, traffic)
        zone_world = affine_transform(zone, inverse(frame))
        upstream_world = affine_transform(upstream, inverse(frame))
        items, mask_up, mask_down, row_hits = [], 0, 0, []
        for si in sorted(tree.query(zone_world)):
            s = spaces[si]
            lg = frame.local(s.geom)
            ll = frame.local(s.line) if s.line is not None else None
            r = count_places(s, lg, ll, zone, upstream)
            if not r:
                continue
            nb, side = r
            items.append([s.cat, LABELS.index(s.label), nb, side])
            if side == SIDE_UP:
                mask_up |= s.cat
            else:
                mask_down |= s.cat
            row_hits.append((si, nb, side, zone_world, upstream_world))
        lon, lat = TO_WGS.transform(frame.mx, frame.my)
        rows.append(
            [
                round(lat, 6),
                round(lon, 6),
                ci,
                qi,
                mask_up,
                mask_down,
                items,
                c["type"],
                c["flags"],
                road,
            ]
        )
        st.append([sid, angle, e1, e2])
        hits.append(row_hits)
    return {
        "communes": communes,
        "quartiers": quartiers,
        "rows": rows,
        "streets": streets,
        "st": st,
        "hits": hits,
    }


def inverse(frame):
    """Affine matrix from the crossing frame back to Lambert-93."""
    ux, uy, dx, dy = frame.ux, frame.uy, frame.dx, frame.dy
    return [ux, dx, uy, dy, frame.mx, frame.my]


def removal(rows, hits, spaces):
    """Places to remove per commune and quartier and per category:
    [upstream (the law), anywhere in the zones (the recommendation)].

    Each space is counted once per area, by the places it has within the
    union of the zones (or their upstream parts) of the crossings it
    affects there: a space between two crossings is not counted twice,
    and a strip running past both sides of a crossing counts in full."""
    out = {"c": {}, "q": {}}
    for scope, idx in (("c", 2), ("q", 3)):
        zones = defaultdict(lambda: defaultdict(lambda: ([], [])))
        for row, hs in zip(rows, hits):
            if row[idx] < 0:
                continue
            for si, _, side, zone, upstream in hs:
                z, u = zones[row[idx]][si]
                z.append(zone)
                if side == SIDE_UP:
                    u.append(upstream)
        for k, by_space in zones.items():
            tot = {}
            for si, (z, u) in by_space.items():
                sp = spaces[si]
                t = tot.setdefault(sp.cat, [0, 0])
                t[1] += places_in(
                    sp, sp.geom.intersection(unary_union(z)).area
                )
                if u:
                    t[0] += places_in(
                        sp, sp.geom.intersection(unary_union(u)).area
                    )
            out[scope][str(k)] = {str(cat): v for cat, v in tot.items()}
    return out


def fold(s):
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def load_crossings(path):
    out = []
    for f in load_geojson(path):
        p, g = f["properties"], f["geometry"]
        if not g or g.get("type") != "LineString" or not p.get("commune"):
            log(
                f"  skipping crossing {p.get('gid')}: "
                "no commune, or not a single line"
            )
            continue
        t = p.get("typetraversee")
        if t and t not in TYPES:
            TYPES.append(t)
        out.append(
            {
                "gid": p["gid"],
                "line": to_l93(shape(g)),
                "commune": p["commune"],
                "quartier": tidy_quartier(p.get("quartier")),
                "type": TYPES.index(t) if t else -1,
                "flags": (
                    (p.get("bev") == "oui") * 1 + (p.get("ilot") == "oui") * 2
                ),
            }
        )
    # Ids order the rows and link the history: they must be unique.
    seen, dup = set(), set()
    for c in out:
        (dup if c["gid"] in seen else seen).add(c["gid"])
    if dup:
        sys.exit(f"Duplicate crossing ids in the source: {sorted(dup)}")
    return out


def gid_key(gid):
    return (0, int(gid), "") if gid.isdigit() else (1, 0, gid)


def order_crossings(
    crossings, order_path, previous_path, alias=None, order=None
):
    """Sort crossings so that published row indices stay put.

    Permalinks (#passage-N) and exported ids are row indices, so rows
    keep the order of the last update: order, the ids of the latest
    snapshot, else those recorded in order_path. New crossings go at the
    end. A deleted crossing still shifts the rows after it. Without
    either, the order is recovered from the published data.json by
    position.

    alias, given only with order, maps a crossing's id to the id it had
    in that snapshot when the two were linked by position (renumbered
    or swapped ids): the crossing then keeps that row. An id whose row
    went to another crossing that way counts as new. An id that moved
    and was not linked keeps its row, so that the rows after it don't
    shift; the generator warns about it."""
    if order is None:
        alias = None
        if order_path.exists():
            order = json.loads(order_path.read_text(encoding="utf-8"))
        else:
            order = order_from_positions(crossings, previous_path)
    rank = {gid: i for i, gid in enumerate(order)}
    alias = alias or {}
    claimed = set(alias.values())

    def key(c):
        g = c["gid"]
        if g in alias:
            return alias[g]
        return None if g in claimed else g

    keys = {c["gid"]: key(c) for c in crossings}
    gone = len(set(rank) - set(keys.values()))
    new = sum(1 for k in keys.values() if k not in rank)
    log(f"  row order: {len(rank)} known, {new} new, {gone} removed")
    crossings.sort(
        key=lambda c: (
            keys[c["gid"]] not in rank,
            rank.get(keys[c["gid"]], 0),
            gid_key(c["gid"]),
        )
    )


def position(line):
    """A crossing's published position, as in data.json rows."""
    lon, lat = TO_WGS.transform(line.centroid.x, line.centroid.y)
    return round(lat, 6), round(lon, 6)


def link_previous(crossings, archive, order_path, report=True):
    """Link the crossings to the latest snapshot, checking that every
    id still lies where it was (logged if report).

    The latest snapshot, today's included after an earlier run today,
    is the one the current data.json rows follow, so it gives the row
    order. Returns (order, alias, hard) for order_crossings: order is
    None without a snapshot, and hard says an id moved and could not be
    repaired. Stops if the order file disagrees with the snapshot: a
    discarded update left its snapshot behind."""
    snaps = H.load_archive(archive)
    if not snaps:
        log("  no snapshot yet: ids not checked")
        return None, {}, False
    last = snaps[-1]
    order = [r[6] for r in last["rows"]]
    if order_path.exists() and (
        json.loads(order_path.read_text(encoding="utf-8")) != order
    ):
        sys.exit(
            f"{order_path.name} does not follow the latest snapshot,"
            f" {last['generated']}. If that update was discarded, delete"
            " its snapshot. Nothing was written."
        )
    old = H.triples(last)
    cur = [(c["gid"], *position(c["line"])) for c in crossings]
    lk = H.link(old, cur)
    if report:
        H.describe(lk, old, cur, f"ids {last['generated']}")
    alias = {cur[j][0]: old[i][0] for j, i in lk.pairs.items()}
    return order, alias, lk.hard


def order_from_positions(crossings, previous_path):
    """Crossing ids in the row order of a data.json without ids, matched
    by position (exactly, else the nearest within 3 m)."""
    if not previous_path.exists():
        return []
    rows = json.loads(previous_path.read_text(encoding="utf-8"))["rows"]
    where = {}
    for c in crossings:
        lon, lat = TO_WGS.transform(c["line"].centroid.x, c["line"].centroid.y)
        where.setdefault((round(lat, 6), round(lon, 6)), c["gid"])
    order, used, missing = [None] * len(rows), set(), []
    for i, r in enumerate(rows):
        gid = where.get((r[0], r[1]))
        if gid and gid not in used:
            order[i] = gid
            used.add(gid)
        else:
            missing.append(i)
    rest = [c for c in crossings if c["gid"] not in used]
    tree = STRtree([c["line"].centroid for c in rest])
    for i in missing:
        x, y = TO_L93.transform(rows[i][1], rows[i][0])
        j = tree.nearest(Point(x, y))
        c = rest[j] if j is not None else None
        if (
            c
            and c["gid"] not in used
            and c["line"].centroid.distance(Point(x, y)) <= 3.0
        ):
            order[i] = c["gid"]
            used.add(c["gid"])
    return [g for g in order if g]


def commune_shapes(communes):
    feats = load_geojson(COMMUNES_GEOJSON)
    by_name = {fold(f["properties"]["n"]): f for f in feats}
    out = []
    for i, name in enumerate(communes):
        f = by_name.get(fold(name))
        if not f:
            sys.exit(f"No contour for commune {name!r} in {COMMUNES_GEOJSON}")
        out.append(
            {
                "type": "Feature",
                "properties": {"i": i, "n": name},
                "geometry": f["geometry"],
            }
        )
    return {"type": "FeatureCollection", "features": out}


# ---------------------------------------------------------------- output


def update_config_dates(path, dates):
    """Update the "date" of sources whose url is in dates, in place.

    config.json is hand-maintained and its key order matters, so only the
    date strings are replaced; the file is not re-serialised."""
    text = path.read_text(encoding="utf-8")
    new = text
    for url, date in dates.items():
        # Dates come from remote metadata: never let one inject text.
        if not (
            isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)
        ):
            log(f"  ignoring malformed date {date!r} for {url}")
            continue
        pat = re.compile(
            r'("url":\s*"'
            + re.escape(url)
            + r'",\s*"date":\s*")\d{4}-\d{2}-\d{2}(")'
        )
        new = pat.sub(lambda m: m.group(1) + date + m.group(2), new)
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def dump(data):
    # The file is inlined into a <script>: "<" never appears raw, so it
    # cannot close the element or open a comment.
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--cache",
        type=Path,
        default=DEFAULT_CACHE,
        help="download directory (default: %(default)s)",
    )
    ap.add_argument(
        "--offline",
        action="store_true",
        help="reuse the files already in the cache",
    )
    ap.add_argument("--out", type=Path, default=VILLE / "data.json")
    ap.add_argument(
        "--debug",
        type=Path,
        help="also write per-crossing details (space ids) here",
    )
    ap.add_argument(
        "--no-config",
        action="store_true",
        help="leave config.json source dates alone",
    )
    args = ap.parse_args(argv)

    # bounding box of the metropolis, with a margin for roads at its edge
    paths = fetch(args.cache, args.offline, (47.10, -1.84, 47.36, -1.36))
    log("Reading inputs")
    crossings = load_crossings(paths[DS_CROSSINGS][0])
    today = datetime.date.today().isoformat()
    site = args.out.resolve() == (VILLE / "data.json").resolve()
    # Writing the site's data, the history rebuild reports the link from
    # the previous date; else report the link to the latest snapshot.
    order, alias, hard = link_previous(
        crossings, H.ARCHIVE, ORDER_FILE, report=not site
    )
    order_crossings(crossings, ORDER_FILE, VILLE / "data.json", alias, order)
    spaces = load_spaces(paths)
    roads = Roads(paths["osm"])
    log(
        f"  {len(crossings)} crossings, {len(spaces)} spaces, "
        f"{len(roads.ways)} OSM ways ({roads.date})"
    )
    log("Computing")
    r = compute(crossings, spaces, roads)
    data = {
        "generated": today,
        "params": {"dist": DIST, "lat": LAT, "min_area": MIN_AREA},
        "meta": {
            "source_passages": "Traversées piétonnes (Nantes Métropole)",
            "source_stationnement": "Emplacements payants, gratuits "
            "matérialisés, réservés, aires de livraison et places PMR "
            "(Nantes Métropole)",
        },
        "cats": CATS,
        "labels": LABELS,
        "communes": r["communes"],
        "quartiers": r["quartiers"],
        "fields": [
            "lat",
            "lon",
            "commune",
            "quartier",
            "mask_amont",
            "mask_aval",
            "places[cat,label,nb,cote]",
            "type",
            "flags(1=bande d'éveil,2=îlot)",
            "road(0 double sens,1 sens unique+DSC,2 sens unique)",
        ],
        "types": TYPES,
        "rows": r["rows"],
        "removal": removal(r["rows"], r["hits"], spaces),
        "geo": commune_shapes(r["communes"]),
        "counts": {"passages": len(r["rows"]), "emplacements": len(spaces)},
        "streets": r["streets"],
        "st": r["st"],
    }
    dates = {"https://www.openstreetmap.org/": roads.date}
    for ds in DATASETS:
        meta = json.loads(paths[ds][1].read_text(encoding="utf-8"))
        modified = meta["metas"]["default"].get("modified")
        if isinstance(modified, str):
            url = f"https://data.nantesmetropole.fr/explore/dataset/{ds}/"
            dates[url] = modified[:10]
    save(args.out, dump(data).encode("utf-8"))
    log(f"Wrote {args.out}")
    if site:
        gids = [c["gid"] for c in crossings]
        save(ORDER_FILE, (json.dumps(gids) + "\n").encode("utf-8"))
        log(f"Wrote {ORDER_FILE}")
        H.ARCHIVE.mkdir(parents=True, exist_ok=True)
        snap = H.snapshot(data, gids, METHODE, dates)
        out = H.ARCHIVE / f"{today}.json"
        save(out, H.dump_snapshot(snap).encode("utf-8"))
        log(f"Wrote {out}")
        log("History")
        # Reports the link from the previous date, also when this run
        # replaced an earlier snapshot of today.
        hard |= H.rebuild(report_all=False)[1]
    if args.debug:
        args.debug.write_text(
            json.dumps(
                [
                    {
                        "gid": c["gid"],
                        "hits": [(spaces[h[0]].key, h[1], h[2]) for h in hs],
                    }
                    for c, hs in zip(crossings, r["hits"])
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    if not args.no_config:
        if update_config_dates(VILLE / "config.json", dates):
            log("Updated source dates in config.json")
    if hard:
        log(
            "\n" + "!" * 72 + "\nWARNING: some crossing ids moved and could"
            " not be matched by position\n(see WARNING!! above). The files"
            " were written; review before\ncommitting.\n" + "!" * 72
        )
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

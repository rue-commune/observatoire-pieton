"""Unit tests for the Nantes data generator (run by scripts/test.sh).

Geometry is built directly in a crossing's local frame where possible:
the crossing runs along x from -5 to 5 (10 m), so the street runs along
y, and facing +y the +x half is on the right."""

import json
import tempfile
import unittest
from pathlib import Path

from shapely.geometry import LineString, Point, box

import nantes as N

CROSSING = LineString([(-5, 0), (5, 0)])


def frame():
    return N.Frame(CROSSING)


def polygon_space(geom, nb=1):
    return N.Space(("t", "1"), 1, "Payant, zone jaune", geom, nb=nb)


def strip_space(line, forme="Longitudinale"):
    return N.Space(
        ("t", "2"),
        1,
        "Gratuit, longitudinal",
        line.buffer(N.STRIP_WIDTH / 2, cap_style="flat"),
        line=line,
        per_place=N.PLACE_LENGTH[forme],
    )


def place(space, road=N.ROAD_TWO_WAY, traffic=1):
    zone, upstream = frame().regions(road, traffic)
    return N.count_places(space, space.geom, space.line, zone, upstream)


class FrameTest(unittest.TestCase):
    def test_local_frame_is_identity_for_an_x_axis_crossing(self):
        f = frame()
        self.assertEqual((round(f.mx, 9), round(f.my, 9)), (0, 0))
        self.assertAlmostEqual(f.along_street(0, 1), 1)
        self.assertEqual(tuple(round(v, 9) for v in f.point(2, 3)), (2, 3))

    def test_inverse_round_trips(self):
        line = LineString([(1000, 2000), (1003, 2004)])
        f = N.Frame(line)
        from shapely.affinity import affine_transform

        p = affine_transform(f.local(Point(1010, 2020)), N.inverse(f))
        self.assertAlmostEqual(p.x, 1010)
        self.assertAlmostEqual(p.y, 2020)

    def test_out_and_back_line_keeps_its_direction(self):
        f = N.Frame(LineString([(-5, 0), (5, 0), (-5, 0)]))
        self.assertAlmostEqual(abs(f.ux), 1)
        self.assertAlmostEqual(f.length, 10)

    def test_zone_size(self):
        zone, _ = frame().regions(N.ROAD_TWO_WAY, 1)
        # 10 m crossing + 2 x 2.5 m overhang; 3 m crossing + 2 x 4 m
        self.assertEqual(zone.bounds, (-7.5, -5.5, 7.5, 5.5))


class SideTest(unittest.TestCase):
    """Which side a space falls on, under the keep-right rule."""

    def side(self, x, y, **kw):
        return place(polygon_space(box(x - 1, y - 1, x + 1, y + 1)), **kw)[1]

    def test_two_way_upstream_quadrants_are_diagonal(self):
        self.assertEqual(self.side(4, -4), N.SIDE_UP)  # right, behind
        self.assertEqual(self.side(-4, 4), N.SIDE_UP)  # left, ahead
        self.assertEqual(self.side(4, 4), N.SIDE_DOWN)
        self.assertEqual(self.side(-4, -4), N.SIDE_DOWN)

    def test_contraflow_street_is_treated_as_two_way(self):
        kw = {"road": N.ROAD_ONE_WAY_CONTRAFLOW, "traffic": -1}
        self.assertEqual(self.side(4, -4, **kw), N.SIDE_UP)
        self.assertEqual(self.side(4, 4, **kw), N.SIDE_DOWN)

    def test_one_way_upstream_is_where_traffic_comes_from(self):
        kw = {"road": N.ROAD_ONE_WAY, "traffic": 1}  # heading +y
        self.assertEqual(self.side(4, -4, **kw), N.SIDE_UP)
        self.assertEqual(self.side(-4, -4, **kw), N.SIDE_UP)
        self.assertEqual(self.side(4, 4, **kw), N.SIDE_DOWN)
        kw["traffic"] = -1
        self.assertEqual(self.side(-4, 4, **kw), N.SIDE_UP)
        self.assertEqual(self.side(-4, -4, **kw), N.SIDE_DOWN)

    def test_space_on_the_crossing_band_is_upstream(self):
        # mostly downstream, but 1 m² within the 3 m crossing band
        space = polygon_space(box(3, 1, 5, 4))  # y 1..1.5 is the band
        self.assertEqual(place(space)[1], N.SIDE_UP)


class CountTest(unittest.TestCase):
    def test_space_needs_half_a_square_metre_in_the_zone(self):
        far = polygon_space(box(3, 5.3, 5, 8))  # 0.4 m² inside
        near = polygon_space(box(3, 5.2, 5, 8))  # 0.6 m² inside
        self.assertIsNone(place(far))
        self.assertIsNotNone(place(near))

    def test_strip_places_from_overlap_length(self):
        # 4 m of longitudinal strip in the downstream quadrant: 1 place
        s = strip_space(LineString([(6, 1.5), (6, 5.5)]))
        self.assertEqual(place(s), (1, N.SIDE_DOWN))
        # the same length of angled parking: 2.5 m per place, so 2
        s = strip_space(LineString([(6, 1.5), (6, 5.5)]), "Epi ou Bataille")
        self.assertEqual(place(s), (2, N.SIDE_DOWN))

    def test_strip_just_outside_the_zone_still_counts(self):
        # centre line 0.5 m beyond the zone edge, half-width 1.1 m
        s = strip_space(LineString([(8, -5), (8, -2)]))
        self.assertEqual(place(s), (1, N.SIDE_UP))

    def test_strip_of_the_cross_street_is_ignored(self):
        s = strip_space(LineString([(-7, 4), (7, 4)]))
        self.assertIsNone(place(s))

    def test_multi_place_space_counts_in_proportion(self):
        # 4 places, half of the space downstream of the crossing
        s = polygon_space(box(3, 2, 5, 9), nb=4)
        self.assertEqual(place(s), (2, N.SIDE_DOWN))


class RemovalTest(unittest.TestCase):
    def test_space_shared_by_two_crossings_counts_once(self):
        space = polygon_space(box(0, 0, 2, 2))
        zone = box(-10, -10, 10, 10)
        rows = [[0, 0, 0, -1], [0, 0, 0, -1]]
        hits = [
            [(0, 1, N.SIDE_UP, zone, zone)],
            [(0, 1, N.SIDE_DOWN, zone, zone)],
        ]
        out = N.removal(rows, hits, [space])
        self.assertEqual(out, {"c": {"0": {"1": [1, 1]}}, "q": {}})


class OrderTest(unittest.TestCase):
    def test_known_rows_keep_their_index_and_new_ones_go_last(self):
        crossings = [{"gid": g} for g in ("30", "5", "20", "10")]
        with tempfile.TemporaryDirectory() as d:
            order = Path(d) / "order.json"
            order.write_text('["20", "99", "10", "30"]', encoding="utf-8")
            N.order_crossings(crossings, order, Path(d) / "absent.json")
        # 99 was removed; 5 is new
        self.assertEqual(
            [c["gid"] for c in crossings], ["20", "10", "30", "5"]
        )


class DividedRoadTest(unittest.TestCase):
    """Two carriageways running north-south, 8 m apart near Nantes."""

    def roads(self, tags_west, tags_east):
        def lonlat(x, y):
            return N.TO_WGS.transform(x, y)

        x0, y0 = N.TO_L93.transform(-1.55, 47.21)
        nodes = [
            (1, x0 - 4, y0 - 50),
            (2, x0 - 4, y0 + 50),
            (3, x0 + 4, y0 - 50),
            (4, x0 + 4, y0 + 50),
        ]
        elements = [
            {
                "type": "node",
                "id": i,
                "lon": lonlat(x, y)[0],
                "lat": lonlat(x, y)[1],
            }
            for i, x, y in nodes
        ]
        elements += [
            {"type": "way", "id": 10, "nodes": [1, 2], "tags": tags_west},
            {"type": "way", "id": 11, "nodes": [3, 4], "tags": tags_east},
        ]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "osm.json"
            p.write_text(
                json.dumps(
                    {
                        "osm3s": {
                            "timestamp_osm_base": "2026-11-20T00:00:00Z"
                        },
                        "elements": elements,
                    }
                ),
                encoding="utf-8",
            )
            roads = N.Roads(p)
        line = LineString([(x0 - 8, y0), (x0 + 8, y0)])
        return roads.crossed_way(line, N.Frame(line))

    def test_opposite_one_way_carriageways_are_dual(self):
        base = {"highway": "primary", "name": "Boulevard", "oneway": "yes"}
        # both drawn northwards, the east one tagged against its geometry
        found = self.roads(base, dict(base, oneway="-1"))
        self.assertTrue(found[3])

    def test_same_direction_one_ways_are_not_dual(self):
        base = {"highway": "primary", "name": "Boulevard", "oneway": "yes"}
        self.assertFalse(self.roads(base, base)[3])


class OsmTagsTest(unittest.TestCase):
    def test_oneway(self):
        self.assertEqual(N.is_oneway({"oneway": "yes"}), 1)
        self.assertEqual(N.is_oneway({"oneway": "-1"}), -1)
        self.assertEqual(N.is_oneway({"junction": "roundabout"}), 1)
        self.assertEqual(
            N.is_oneway({"junction": "roundabout", "oneway": "no"}), 0
        )
        self.assertEqual(N.is_oneway({"highway": "residential"}), 0)

    def test_contraflow(self):
        self.assertTrue(N.has_contraflow({"oneway:bicycle": "no"}))
        self.assertTrue(N.has_contraflow({"cycleway:left": "opposite_lane"}))
        self.assertFalse(N.has_contraflow({"cycleway:left": "lane"}))


class TextTest(unittest.TestCase):
    def test_tidy_quartier(self):
        self.assertEqual(N.tidy_quartier("Centre - Bourg"), "Centre – Bourg")
        self.assertEqual(
            N.tidy_quartier("Bourg/Secteur rural"), "Bourg / Secteur rural"
        )
        self.assertEqual(
            N.tidy_quartier("Beautour/ Les Rives"), "Beautour / Les Rives"
        )
        self.assertIsNone(N.tidy_quartier(None))

    def test_dump_cannot_close_the_script_element(self):
        text = N.dump({"a": "</script><!-- x"})
        self.assertNotIn("<", text)
        self.assertEqual(json.loads(text), {"a": "</script><!-- x"})

    def test_update_config_dates_touches_only_the_date(self):
        src = (
            '{\n "z": 1,\n "sources": [\n  {\n   "nom": "OSM",\n'
            '   "url": "https://osm.example/",\n   "date": "2026-01-01"\n'
            '  },\n  {\n   "nom": "X",\n   "url": "https://x.example/"\n'
            "  }\n ]\n}"
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            p.write_text(src, encoding="utf-8")
            changed = N.update_config_dates(
                p,
                {
                    "https://osm.example/": "2026-11-20",
                    "https://x.example/": "2026-11-20",
                },
            )
            self.assertTrue(changed)
            self.assertEqual(
                p.read_text(encoding="utf-8"),
                src.replace("2026-01-01", "2026-11-20"),
            )

    def test_update_config_dates_rejects_malformed_dates(self):
        src = '{"url": "https://osm.example/", "date": "2026-01-01"}'
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            p.write_text(src, encoding="utf-8")
            self.assertFalse(
                N.update_config_dates(p, {"https://osm.example/": 'x","y":"z'})
            )
            self.assertEqual(p.read_text(encoding="utf-8"), src)


if __name__ == "__main__":
    unittest.main()

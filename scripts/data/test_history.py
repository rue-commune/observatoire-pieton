"""Unit tests for the snapshot archive and history (run by scripts/test.sh).

Positions are near Nantes; 1e-5 degrees of latitude is about 1.1 m."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import compare
import history as H

LAT, LON = 47.2, -1.55


def at(dn):
    """A position dn * 1e-5 degrees north of the reference point."""
    return round(LAT + dn * 1e-5, 6), LON


def snap(date, rows, methode=1, communes=("A", "B")):
    """rows: (gid, dn, commune index, up mask, down mask)."""
    return {
        "generated": date,
        "methode": methode,
        "sources": {},
        "communes": list(communes),
        "quartiers": [],
        "removal": {"c": {"0": {"1": [2, 3]}, "1": {"1": [1, 1]}}},
        "fields": H.SNAPSHOT_FIELDS,
        "rows": [[*at(dn), c, -1, up, down, g] for g, dn, c, up, down in rows],
    }


def triples(rows):
    return [(g, *at(dn)) for g, dn in rows]


class LinkTest(unittest.TestCase):
    def test_same_ids_same_places_link_by_id(self):
        t = triples([("1", 0), ("2", 100)])
        lk = H.link(t, t)
        self.assertEqual(lk.pairs, {0: 0, 1: 1})
        self.assertEqual((lk.repaired, lk.new, lk.gone), ([], [], []))
        self.assertFalse(lk.hard)

    def test_redrawn_in_place_keeps_its_link(self):
        lk = H.link(triples([("1", 0)]), triples([("1", 1)]))  # 1.1 m
        self.assertEqual((lk.pairs, lk.shifted, lk.moved), ({0: 0}, 1, []))

    def test_swapped_ids_are_repaired_by_position(self):
        old = triples([("1", 0), ("2", 100)])
        new = triples([("2", 0), ("1", 100)])
        lk = H.link(old, new)
        self.assertEqual(lk.pairs, {0: 0, 1: 1})
        self.assertEqual(len(lk.moved), 2)
        self.assertEqual(sorted(lk.repaired), [(0, 0), (1, 1)])
        self.assertFalse(lk.hard)

    def test_renumbered_id_is_repaired_by_position(self):
        lk = H.link(triples([("1", 0)]), triples([("9", 0)]))
        self.assertEqual((lk.pairs, lk.repaired), ({0: 0}, [(0, 0)]))
        self.assertEqual((lk.new, lk.gone), ([], []))

    def test_id_moved_to_an_empty_place_is_hard(self):
        old = triples([("1", 0), ("2", 500)])
        new = triples([("1", 100), ("2", 500)])
        lk = H.link(old, new)
        self.assertTrue(lk.hard)
        self.assertEqual([m[0] for m in lk.unrepaired], ["1"])
        self.assertEqual((lk.pairs, lk.new, lk.gone), ({1: 1}, [0], [0]))

    def test_id_moved_onto_a_vanished_crossing_is_repaired(self):
        # 1 now lies where 2 was, and 2 is gone: a renumbering.
        old = triples([("1", 0), ("2", 100)])
        new = triples([("1", 100)])
        lk = H.link(old, new)
        self.assertFalse(lk.hard)
        self.assertEqual((lk.pairs, lk.gone), ({0: 1}, [0]))

    def test_position_matching_is_one_to_one_nearest_first(self):
        old = triples([("1", 0)])
        new = triples([("8", 2), ("9", 1)])
        lk = H.link(old, new)
        self.assertEqual((lk.pairs, lk.new), ({1: 0}, [0]))

    def test_too_far_is_not_matched(self):
        lk = H.link(triples([("1", 0)]), triples([("9", 3)]))  # 3.3 m
        self.assertEqual((lk.pairs, lk.new, lk.gone), ({}, [0], [0]))


class SnapshotTest(unittest.TestCase):
    def test_dump_round_trips_one_crossing_per_line(self):
        s = snap("2027-01-15", [("1", 0, 0, 1, 0), ("2", 100, 1, 0, 0)])
        text = H.dump_snapshot(s)
        self.assertEqual(json.loads(text), s)
        self.assertIn('\n[47.2,-1.55,0,-1,1,0,"1"],\n', text)
        H.check_snapshot(json.loads(text), "t")

    def test_check_rejects_duplicate_ids(self):
        s = snap("2027-01-15", [("1", 0, 0, 0, 0), ("1", 100, 0, 0, 0)])
        with self.assertRaises(ValueError):
            H.check_snapshot(s, "t")

    def test_archive_file_name_must_match_its_date(self):
        with tempfile.TemporaryDirectory() as d:
            s = snap("2027-01-15", [("1", 0, 0, 0, 0)])
            (Path(d) / "2027-01-16.json").write_text(H.dump_snapshot(s))
            with self.assertRaises(ValueError):
                H.load_archive(d)

    def test_snapshot_keeps_row_order_and_adds_ids(self):
        data = {
            "generated": "2027-01-15",
            "communes": ["A"],
            "quartiers": [],
            "removal": {"c": {}, "q": {}},
            "rows": [[47.2, -1.5, 0, -1, 1, 0, [], 0, 0, 0]],
        }
        s = H.snapshot(data, ["42"], 1, {"u": "2027-01-01"})
        self.assertEqual(s["rows"], [[47.2, -1.5, 0, -1, 1, 0, "42"]])


class BuildTest(unittest.TestCase):
    def setUp(self):
        a = snap(
            "2027-01-15",
            [
                ("1", 0, 0, 1, 0),  # ko, then mid
                ("2", 100, 0, 1, 0),  # ko throughout
                ("3", 200, 1, 0, 0),  # ok, ko after a method change
            ],
        )
        b = snap(
            "2027-02-15",
            [("1", 0, 0, 0, 1), ("2", 100, 0, 1, 0), ("3", 200, 1, 0, 0)],
        )
        c = snap(
            "2027-03-15",
            [
                ("1", 0, 0, 0, 1),
                ("2", 100, 0, 1, 0),
                ("3", 200, 1, 1, 0),
                ("4", 300, 1, 0, 0),  # new
            ],
            methode=2,
        )
        self.snaps = [a, b, c]
        self.h = H.build(self.snaps)

    def test_changes_say_where_the_current_status_began(self):
        self.assertEqual(
            self.h["changes"],
            [[0, 1, H.KO], [2, 2, H.METHOD], [3, 2, H.NEW]],
        )

    def test_series_count_statuses_per_date_and_commune(self):
        self.assertEqual(
            self.h["series"]["total"], [[2, 0, 1], [1, 1, 1], [2, 1, 1]]
        )
        self.assertEqual(
            self.h["series"]["communes"]["B"],
            [[0, 0, 1], [0, 0, 1], [1, 0, 1]],
        )
        self.assertEqual(self.h["removal"][0], {"1": [3, 4]})
        self.assertEqual(self.h["methodes"], [1, 1, 2])

    def test_flapping_counts_returns_to_an_earlier_status(self):
        def flips(snaps):
            links = [None] + [
                H.link(H.triples(x), H.triples(y))
                for x, y in zip(snaps, snaps[1:])
            ]
            return H.flapping(snaps, links)

        a, b = self.snaps[:2]
        # 1 went ko, mid, ko: one flip; a lasting change is not one
        self.assertEqual(flips([a, b, dict(a, generated="2027-03-15")]), 1)
        self.assertEqual(flips([a, b, dict(b, generated="2027-03-15")]), 0)

    def test_rebuild_reports_an_unrepaired_id_in_the_latest_link(self):
        a = snap("2027-01-15", [("1", 0, 0, 0, 0)])
        b = snap("2027-02-15", [("1", 100, 0, 0, 0)])
        with tempfile.TemporaryDirectory() as d:
            for s in (a, b):
                p = Path(d) / f"{s['generated']}.json"
                p.write_text(H.dump_snapshot(s))
            out = Path(d) / "history.json"
            hist, hard = H.rebuild(Path(d), out)
            self.assertTrue(hard)
            self.assertEqual(json.loads(out.read_text()), hist)
        self.assertEqual(hist["changes"], [[0, 1, H.NEW]])


class CompareTest(unittest.TestCase):
    def compare(self, a, b):
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for name, s in (("a", a), ("b", b)):
                paths.append(Path(d) / f"{name}.json")
                paths[-1].write_text(json.dumps(s))
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(
                out
            ):
                return compare.main([str(p) for p in paths]), out.getvalue()

    def test_snapshots_are_matched_by_id(self):
        a = snap("2027-01-15", [("1", 0, 0, 1, 0), ("2", 100, 0, 0, 0)])
        b = snap("2027-02-15", [("2", 100, 0, 0, 0), ("1", 0, 0, 0, 0)])
        code, out = self.compare(a, b)
        self.assertEqual(code, 0)
        self.assertIn("ko -> ok  1", out)

    def test_an_unrepaired_id_fails(self):
        a = snap("2027-01-15", [("1", 0, 0, 0, 0)])
        b = snap("2027-02-15", [("1", 100, 0, 0, 0)])
        code, out = self.compare(a, b)
        self.assertEqual(code, 3)
        self.assertIn("WARNING!! id 1", out)

    def test_a_snapshot_and_a_data_file_are_not_compared(self):
        a = snap("2027-01-15", [("1", 0, 0, 0, 0)])
        b = {"generated": "2027-02-15", "rows": []}
        with self.assertRaises(SystemExit):
            self.compare(a, b)


class CommittedHistoryTest(unittest.TestCase):
    def test_history_json_is_built_from_the_archive(self):
        if not list(H.ARCHIVE.glob("*.json")):
            self.skipTest("no snapshots yet")
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "history.json"
            H.rebuild(H.ARCHIVE, out)
            self.assertEqual(
                out.read_text(encoding="utf-8"),
                H.HISTORY.read_text(encoding="utf-8"),
                "history.json differs from the archive: run history.py",
            )


if __name__ == "__main__":
    unittest.main()

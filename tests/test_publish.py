from fractions import Fraction as F
from gridarchive import Conflict, NotFound, ValidationError
from .support import DiskCase, counts, rectangle


class PublishTests(DiskCase):
    def test_reopen_raw_and_receipt(self):
        cells = {"s": [[("0/2", 0), (2, 0), (2, "2/1"), (0, 2), ("0/2", 0)]]}
        revision = self.archive.publish_grid("daily", "request", cells)
        field = self.archive.put_field("value", revision, {"s": 12})
        before = counts(self.archive)
        self.reopen()
        grid = self.archive.read_grid(revision)
        self.assertEqual(grid["cells"]["s"][0][0], (F(0), F(0)))
        self.assertEqual(grid["raw"]["s"][0][0], ["0/2", "0"])
        self.assertEqual(self.archive.read_field(field)["values"], {"s": F(12)})
        self.assertEqual(self.archive.publish_grid("daily", "request", cells), revision)
        self.assertEqual(self.archive.grid_receipt("request"), revision)
        self.assertEqual(counts(self.archive), before)

    def test_invalid_overlap_keeps_head_and_no_receipt(self):
        good = {"old": [rectangle(0, 0, 2, 2)]}
        revision = self.archive.publish_grid("grid", "good", good)
        before = counts(self.archive)
        with self.assertRaises(ValidationError):
            self.archive.publish_grid("grid", "bad", {
                "a": [rectangle(0, 0, 2, 2)], "b": [rectangle(1, 0, 3, 2)]})
        self.assertEqual(self.archive.head("grid"), revision)
        self.assertEqual(counts(self.archive), before)
        with self.assertRaises(NotFound):
            self.archive.grid_receipt("bad")
        self.reopen()
        self.assertEqual(self.archive.read_grid(revision)["cells"]["old"][0][2], (F(2), F(2)))

    def test_edge_touch_and_hole_island_are_valid(self):
        revision = self.archive.publish_grid("donut", "donut-1", {
            "donut": [rectangle(0, 0, 4, 4), rectangle(1, 1, 3, 3)],
            "island": [rectangle(1, 1, 3, 3)]})
        self.assertEqual(set(self.archive.read_grid(revision)["cells"]), {"donut", "island"})

    def test_replay_does_not_restore_old_head(self):
        first = self.archive.publish_grid("g", "one", {"a": [rectangle(0, 0, 2, 2)]})
        second = self.archive.publish_grid("g", "two", {"b": [rectangle(3, 0, 4, 1)]})
        self.assertEqual(self.archive.publish_grid("g", "one", {"a": [rectangle(0, 0, 2, 2)]}), first)
        self.assertEqual(self.archive.head("g"), second)
        with self.assertRaises(Conflict):
            self.archive.publish_grid("elsewhere", "one", {"a": [rectangle(0, 0, 2, 2)]})
        self.assertEqual(self.archive.head("g"), second)

    def test_zero_invalid_coordinates_and_edge_budget(self):
        before = counts(self.archive)
        for cells in (
            {"x": [[(0, 0), (1, 0), (0, 0)]]},
            {"x": [[(0, 0), (1, 0), (1, 1)]]},
            {"x": [rectangle(0.0, 0, 1, 1)]},
            {"x": [rectangle(True, 0, 2, 2)]},
            {"x": [rectangle("1/0", 0, 2, 2)]},
            {"x": [rectangle(0, 0, 1, 1)] * 11},
        ):
            with self.subTest(cells=cells), self.assertRaises(ValidationError):
                self.archive.publish_grid("bad", "bad", cells)
        self.assertEqual(counts(self.archive), before)

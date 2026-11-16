from fractions import Fraction as F
from gridarchive import Conflict, NotFound, ValidationError
from .support import MemoryCase, counts, rectangle


class FieldTests(MemoryCase):
    def test_complete_binding_and_replay(self):
        grid = self.archive.publish_grid("g", "g", {
            "zero": [rectangle(0, 0, 1, 1)], "missing": [rectangle(1, 0, 2, 1)]})
        field = self.archive.put_field("f", grid, {"zero": 0, "missing": None})
        before = counts(self.archive)
        self.assertEqual(self.archive.read_field(field), {
            "id": field, "grid": grid, "values": {"zero": F(0), "missing": None}})
        self.assertEqual(self.archive.put_field("f", grid, {"missing": None, "zero": "0/2"}), field)
        self.assertEqual(self.archive.field_receipt("f"), field)
        with self.assertRaises(Conflict):
            self.archive.put_field("f", grid, {"zero": None, "missing": 0})
        self.assertEqual(counts(self.archive), before)

    def test_wrong_cells_no_version_no_receipt(self):
        grid = self.archive.publish_grid("g", "g", {"old": [rectangle(0, 0, 1, 1)]})
        other = self.archive.publish_grid("g", "g2", {"new": [rectangle(0, 0, 2, 1)]})
        before = counts(self.archive)
        for values in ({"new": 1}, {}, {"old": 1, "new": None}, {"old": 0.5}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.archive.put_field("invalid", grid, values)
        self.assertEqual(counts(self.archive), before)
        with self.assertRaises(NotFound):
            self.archive.field_receipt("invalid")
        self.assertEqual(set(self.archive.read_grid(other)["cells"]), {"new"})

    def test_fraction_and_negative_total(self):
        grid = self.archive.publish_grid("g", "g", {"x": [rectangle(0, 0, 1, 1)]})
        field = self.archive.put_field("f", grid, {"x": "-2/3"})
        self.assertEqual(self.archive.read_field(field)["values"]["x"], -F(2, 3))
        with self.assertRaises(NotFound):
            self.archive.put_field("unknown", 1000, {"x": 1})

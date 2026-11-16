from fractions import Fraction as F
from .support import MemoryCase, basic, rectangle


class RemapTests(MemoryCase):
    def test_split_total_and_missing_zero(self):
        source, target, field, job = basic(self.archive)
        result = self.archive.run_job(job)["result"]
        self.assertEqual(result["allocated"], {"small": F(3), "large": F(9),
                                               "unknown": F(0), "zero": F(0)})
        self.assertEqual(result["source_area"], {"mass": F(4), "missing": F(4), "zero": F(1)})
        self.assertEqual(result["overlap_area"]["mass"], {
            "small": F(1), "large": F(3), "unknown": F(0), "zero": F(0)})
        self.assertEqual(result["uncovered"], {"mass": F(0), "zero": F(0)})
        self.assertEqual(result["missing_area"], {"missing": {"unknown": F(2)}})
        self.assertEqual(result["uncovered_missing_area"], {"missing": F(2)})
        self.assertNotIn("missing", result["transfers"])
        self.assertEqual(result["transfers"]["zero"]["zero"], F(0))
        self.assertEqual(self.archive.read_field(field)["grid"], source)
        self.assertEqual(self.archive.read_result(job)["job"]["target"], target)

    def test_partial_uncovered_conservation(self):
        source = self.archive.publish_grid("s", "s", {
            "mass": [rectangle(0, 0, 2, 2)],
            "missing": [rectangle(3, 0, 5, 2)],
            "zero": [rectangle(6, 0, 8, 2)]})
        target = self.archive.publish_grid("t", "t", {
            "a": [rectangle(0, 0, 1, 2)],
            "b": [rectangle(3, 0, 4, 2)],
            "c": [rectangle(6, 0, 7, 2)]})
        field = self.archive.put_field("f", source, {"mass": "5/3", "missing": None, "zero": 0})
        job = self.archive.create_job("partial", source, target, field)
        result = self.archive.run_job(job)["result"]
        self.assertEqual(result["allocated"], {"a": F(5, 6), "b": F(0), "c": F(0)})
        self.assertEqual(result["uncovered"], {"mass": F(5, 6), "zero": F(0)})
        self.assertEqual(result["missing_area"], {"missing": {"b": F(2)}})
        for cell, value in self.archive.read_field(field)["values"].items():
            if value is not None:
                self.assertEqual(sum(result["transfers"][cell].values(), F(0))
                                 + result["uncovered"][cell], value)

    def test_disjoint_signed_and_boundary_contact(self):
        source = self.archive.publish_grid("s", "s", {"s": [rectangle(0, 0, 1, 1)]})
        target = self.archive.publish_grid("t", "t", {"t": [rectangle(1, 0, 2, 1)]})
        field = self.archive.put_field("f", source, {"s": "-7/3"})
        job = self.archive.create_job("touch", source, target, field)
        result = self.archive.run_job(job)["result"]
        self.assertEqual(result["allocated"]["t"], 0)
        self.assertEqual(result["overlap_area"]["s"]["t"], 0)
        self.assertEqual(result["uncovered"]["s"], -F(7, 3))
        self.assertEqual(self.archive.run_job(job)["result"], result)

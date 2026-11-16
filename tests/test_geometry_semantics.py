import unittest
from fractions import Fraction as F
from gridarchive.vendor.sdk1 import Region
from .support import MemoryCase, rectangle


class ScalarGeometryTests(unittest.TestCase):
    def test_even_odd_holes_self_crossings_and_coincident_edges(self):
        square = rectangle(0, 0, 2, 2)
        cases = [
            ([rectangle(0, 0, 4, 4), rectangle(1, 1, 3, 3)], 12),
            ([[(0, 0), (2, 2), (0, 2), (2, 0), (0, 0)]], 2),
            ([square, square], 0),
            ([square, list(reversed(square)), square], 4),
            ([[(0, 0), (2, 0), (2, 2), (0, 2), (0, 0), (-1, 0), (0, 0)]], 4),
            ([rectangle(0, 0, 3, 2), rectangle(1, 0, 4, 2)], 4),
            ([[(0, 0), (1, 0), (2, 0), (2, 2), (0, 2), (0, 0)]], 4),
        ]
        window = Region([rectangle(-10, -10, 10, 10)])
        for rings, area in cases:
            with self.subTest(rings=rings):
                shape = Region(rings)
                self.assertEqual(shape.area(), F(area))
                self.assertEqual(shape.intersection_area(window), F(area))
                self.assertEqual(window.intersection_area(shape), F(area))
                reversed_shape = Region([list(reversed(ring)) for ring in rings])
                self.assertEqual(reversed_shape.area(), F(area))

    def test_rational_triangle_and_intersection(self):
        triangle = Region([[(0, 0), ("3/2", 0), (0, "2/3"), (0, 0)]])
        clip = Region([rectangle(0, 0, "3/4", 1)])
        self.assertEqual(triangle.area(), F(1, 2))
        self.assertEqual(triangle.intersection_area(clip), F(3, 8))
        self.assertEqual(triangle.intersection_area(triangle), F(1, 2))
        touching = Region([rectangle("3/2", 0, 2, 1)])
        self.assertEqual(triangle.intersection_area(touching), F(0))

    def test_tiled_exact_reference_for_parity_rectangles(self):
        # Independent integer unit-square occupancy; no production geometry calls in the oracle.
        for boxes in (
            [(0, 0, 3, 2), (1, 0, 4, 2)],
            [(0, 0, 4, 4), (1, 1, 3, 3), (2, 2, 4, 4)],
            [(-2, -2, 2, 2), (-1, -1, 1, 1), (-1, -1, 1, 1)],
        ):
            occupied = {(x, y) for x in range(-3, 5) for y in range(-3, 5)
                        if sum(a <= x < c and b <= y < d for a, b, c, d in boxes) % 2}
            shape = Region([rectangle(*box) for box in boxes])
            self.assertEqual(shape.area(), len(occupied))
            for window in [(-2, -1, 2, 3), (0, 0, 3, 1), (1, 1, 4, 4)]:
                a, b, c, d = window
                expected = sum(a <= x < c and b <= y < d for x, y in occupied)
                self.assertEqual(shape.intersection_area(Region([rectangle(*window)])), expected)


class GeometryBusinessTests(MemoryCase):
    def test_hole_and_bow_remapping(self):
        for name, rings, total, bottom, top in (
            ("hole", [rectangle(0, 0, 4, 4), rectangle(1, 1, 3, 3)], 24, 12, 12),
            ("bow", [[(0, 0), (2, 2), (0, 2), (2, 0), (0, 0), (-1, 0), (0, 0)]], 10, 5, 5),
        ):
            with self.subTest(name=name):
                boundary = 2 if name == "hole" else 1
                right = 4 if name == "hole" else 2
                source = self.archive.publish_grid(name, name, {"s": rings})
                target = self.archive.publish_grid(name + "-t", name + "-t", {
                    "bottom": [rectangle(0, 0, right, boundary)],
                    "top": [rectangle(0, boundary, right, right)]})
                field = self.archive.put_field(name, source, {"s": total})
                job = self.archive.create_job(name, source, target, field)
                result = self.archive.run_job(job)["result"]
                self.assertEqual(result["allocated"], {"bottom": F(bottom), "top": F(top)})
                self.assertEqual(result["uncovered"]["s"], F(0))
                self.assertEqual(sum(result["overlap_area"]["s"].values()), result["source_area"]["s"])

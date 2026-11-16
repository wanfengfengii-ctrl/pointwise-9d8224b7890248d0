import unittest
from fractions import Fraction as F
from gridarchive import ValidationError
from gridarchive.vendor.sdk2 import Polygon


class ConvexPortTests(unittest.TestCase):
    def test_exact_convex_intersection(self):
        a = Polygon([(0, 0), (2, 0), (0, 2)])
        b = Polygon([(1, 0), (3, 0), (1, 2)])
        self.assertEqual(a.area(), F(2))
        self.assertEqual(a.intersection_area(b), F(1, 2))
        self.assertEqual(b.intersection_area(a), F(1, 2))
        self.assertEqual(a.intersection(b).area(), F(1, 2))
        reversed_a = Polygon(list(reversed(a.vertices)))
        self.assertEqual(reversed_a.area(), a.area())

    def test_containment_disjoint_and_zero_area_contact(self):
        square = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
        triangle = Polygon([(0, 0), (1, 0), (0, 1)])
        touch = Polygon([(2, 0), (3, 0), (3, 2), (2, 2)])
        away = Polygon([(3, 0), (4, 0), (4, 1), (3, 1)])
        self.assertEqual(square.intersection_area(triangle), F(1, 2))
        self.assertIsNone(square.intersection(touch))
        self.assertEqual(square.intersection_area(away), F(0))
        small = Polygon([(0, 0), ("1/3", 0), ("1/3", "1/2"), (0, "1/2")])
        self.assertEqual(small.area(), F(1, 6))

    def test_rejects_nonconvex_and_degenerate(self):
        for points in (
            [(0, 0), (1, 0), (1, 1), (3, 1), (3, 2), (0, 2)],
            [(0, 0), (2, 2), (0, 2), (2, 0)],
            [(0, 0), (1, 0), (2, 0)],
            [(0, 0), (1, 0), (1, 1), (1, 0), (0, 1)],
        ):
            with self.subTest(points=points), self.assertRaises(ValidationError):
                Polygon(points)

    def test_cross_port_exact_convex_reference(self):
        from gridarchive.vendor.sdk1 import Region
        shapes = [
            [(0, 0), (2, 0), (0, 2)],
            [(F(1, 3), -1), (3, F(1, 2)), (F(1, 2), 3)],
            [(-2, -1), (2, -1), (2, 1), (-2, 1)],
            [(0, 0), (1, 0), (2, 0), (2, 2), (0, 2)],
        ]
        for points in shapes:
            old = Region([points + points[:1]])
            new = Polygon(points)
            self.assertEqual(new.area(), old.area())
            for other in shapes:
                other_old = Region([other + other[:1]])
                other_new = Polygon(other)
                self.assertEqual(new.intersection_area(other_new),
                                 old.intersection_area(other_old))

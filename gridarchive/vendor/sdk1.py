"""SDK1: even-odd closed walks, exact scalar area and intersection area.

The evaluator subdivides boundary segments at incidences and integrates the
selected oriented boundary. It exports neither faces nor a polygon conversion.
"""
from fractions import Fraction as F
from itertools import combinations
from ..codec import rational
from ..errors import ValidationError


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def at(a, d, t):
    return (a[0] + d[0] * t, a[1] + d[1] * t)


class Region:
    def __init__(self, rings):
        try:
            parsed = []
            for ring in rings:
                points = []
                for point in ring:
                    if len(point) != 2:
                        raise ValidationError("point requires two coordinates")
                    points.append(tuple(rational(v) for v in point))
                if len(points) < 2 or points[0] != points[-1]:
                    raise ValidationError("walk must be explicitly closed")
                parsed.append(tuple(points))
        except TypeError as exc:
            raise ValidationError("rings must be finite sequences") from exc
        if not parsed:
            raise ValidationError("region requires at least one closed walk")
        self.rings = tuple(parsed)
        self.edge_count = sum(len(r) - 1 for r in self.rings)
        if self.edge_count > 40:
            raise ValidationError("region exceeds 40 input edges")
        self.edges = tuple((a, b) for r in self.rings
                           for a, b in zip(r, r[1:]) if a != b)

    def area(self):
        return _measure((self,))

    def intersection_area(self, other):
        if not isinstance(other, Region):
            raise TypeError("SDK1 requires Region")
        return _measure((self, other))

    def _contains(self, point):
        x, y = point
        odd = False
        for a, b in self.edges:
            if (a[1] > y) != (b[1] > y):
                hit = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                if hit > x:
                    odd = not odd
        return odd


def _parameter(point, a, d):
    k = 0 if d[0] else 1
    return (point[k] - a[k]) / d[k]


def _segments(edges):
    cuts = [{F(0), F(1)} for _ in edges]
    for i, j in combinations(range(len(edges)), 2):
        a, b = edges[i]
        c, e = edges[j]
        d, f = sub(b, a), sub(e, c)
        denominator = cross(d, f)
        if denominator:
            t = cross(sub(c, a), f) / denominator
            u = cross(sub(c, a), d) / denominator
            if 0 <= t <= 1 and 0 <= u <= 1:
                cuts[i].add(t)
                cuts[j].add(u)
        elif cross(sub(c, a), d) == 0:
            for point in (c, e):
                t = _parameter(point, a, d)
                if 0 <= t <= 1:
                    cuts[i].add(t)
            for point in (a, b):
                u = _parameter(point, c, f)
                if 0 <= u <= 1:
                    cuts[j].add(u)
    unique = set()
    for (a, b), values in zip(edges, cuts):
        d = sub(b, a)
        ordered = sorted(values)
        for t, u in zip(ordered, ordered[1:]):
            p, q = at(a, d, t), at(a, d, u)
            if p != q:
                unique.add(tuple(sorted((p, q))))
    return sorted(unique)


def _side_points(a, b, edges):
    middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    d = sub(b, a)
    normal = (-d[1], d[0])
    step = F(1)
    norm = abs(normal[0]) + abs(normal[1])
    for c, e in edges:
        f = sub(e, c)
        denominator = cross(f, normal)
        if denominator:
            t = -cross(f, sub(middle, c)) / denominator
            if t:
                step = min(step, abs(t) / 2)
        for point in (c, e):
            distance = abs(point[0] - middle[0]) + abs(point[1] - middle[1])
            if distance:
                step = min(step, distance / (2 * norm))
    return at(middle, normal, step), at(middle, normal, -step)


def _measure(regions):
    edges = tuple(edge for region in regions for edge in region.edges)
    total = F(0)
    for a, b in _segments(edges):
        left, right = _side_points(a, b, edges)
        inside_left = all(region._contains(left) for region in regions)
        inside_right = all(region._contains(right) for region in regions)
        total += (int(inside_left) - int(inside_right)) * cross(a, b) / 2
    if total < 0:
        raise ArithmeticError("oriented boundary produced negative area")
    return total

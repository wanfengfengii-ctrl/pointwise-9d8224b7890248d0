"""SDK2: positive convex polygons only; exact area and convex clipping."""
from fractions import Fraction as F
from ..codec import rational
from ..errors import ValidationError


def _cross(a, b, c):
    return ((b[0] - a[0]) * (c[1] - a[1])
            - (b[1] - a[1]) * (c[0] - a[0]))


def _signed(points):
    return sum((a[0] * b[1] - a[1] * b[0]
                for a, b in zip(points, points[1:] + points[:1])), F(0)) / 2


class Polygon:
    def __init__(self, vertices):
        try:
            points = []
            for point in vertices:
                if len(point) != 2:
                    raise ValidationError("point requires two coordinates")
                points.append(tuple(rational(v) for v in point))
        except TypeError as exc:
            raise ValidationError("vertices must be a finite sequence") from exc
        if len(points) > 1 and points[0] == points[-1]:
            points.pop()
        if len(points) < 3 or len(set(points)) != len(points):
            raise ValidationError("convex polygon requires distinct vertices")
        signed = _signed(points)
        if signed == 0:
            raise ValidationError("polygon must have positive area")
        if signed < 0:
            points.reverse()
        if any(_cross(a, b, p) < 0
               for a, b in zip(points, points[1:] + points[:1]) for p in points):
            raise ValidationError("SDK2 accepts only convex polygons")
        self.vertices = tuple(points)

    def area(self):
        return _signed(list(self.vertices))

    def intersection(self, other):
        if not isinstance(other, Polygon):
            raise TypeError("SDK2 requires Polygon")
        points = list(self.vertices)
        clip = list(other.vertices)
        for a, b in zip(clip, clip[1:] + clip[:1]):
            if not points:
                return None
            output = []
            for p, q in zip(points, points[1:] + points[:1]):
                p_side, q_side = _cross(a, b, p), _cross(a, b, q)
                if p_side >= 0:
                    output.append(p)
                if (p_side < 0 < q_side) or (q_side < 0 < p_side):
                    t = p_side / (p_side - q_side)
                    output.append((p[0] + t * (q[0] - p[0]),
                                   p[1] + t * (q[1] - p[1])))
            points = []
            for p in output:
                if not points or p != points[-1]:
                    points.append(p)
            if len(points) > 1 and points[0] == points[-1]:
                points.pop()
        if len(points) < 3 or _signed(points) == 0:
            return None
        return Polygon(points)

    def intersection_area(self, other):
        result = self.intersection(other)
        return F(0) if result is None else result.area()

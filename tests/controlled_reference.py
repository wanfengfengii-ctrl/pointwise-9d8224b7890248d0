"""Independent exact reference for controlled remapping tests.

This helper deliberately imports neither gridarchive.lp nor any production
solver. It solves the same controlled transportation problem with a different
exact method built only on Fraction Gaussian elimination.

The feasible flow set is the polyhedron {x >= 0 : A x = b} defined by the
source conservation and target control equalities. The objective
sum_k |x_k - p_k| is piecewise linear with kink hyperplanes x_k = p_k, so an
optimum is attained at a vertex of the polyhedron refined by those kinks. For
every subset of active kinks x_k = p_k we enumerate every basic feasible
solution of the resulting equality system through Gaussian elimination over
every rank-sized choice of columns, evaluate the true absolute deviation
directly, and collect all globally optimal points. Per-flow minima/maxima over
those optimal points are the exact optimal-face ranges.
"""
from fractions import Fraction as F
from itertools import combinations


class ReferenceInfeasible(Exception):
    pass


def _eliminate(matrix, rhs):
    width = len(matrix[0])
    work = [[F(matrix[r][j]) for j in range(width)] + [F(rhs[r])]
            for r in range(len(matrix))]
    pivots = []
    rank = 0
    for col in range(width):
        pivot = next((r for r in range(rank, len(work)) if work[r][col] != 0), None)
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        divisor = F(work[rank][col])
        work[rank] = [work[rank][j] / divisor for j in range(width + 1)]
        for r in range(len(work)):
            if r == rank:
                continue
            factor = work[r][col]
            if factor:
                work[r] = [work[r][j] - factor * work[rank][j]
                           for j in range(width + 1)]
        pivots.append((rank, col))
        rank += 1
    for r in range(rank, len(work)):
        if work[r][-1] != 0:
            return None
    return work, pivots, rank


def _basic_solutions(matrix, rhs, n):
    eliminated = _eliminate(matrix, rhs)
    if eliminated is None:
        return []
    _, _, rank = eliminated
    results = set()
    for columns in combinations(range(n), rank):
        sub = [[matrix[r][j] for j in columns] for r in range(len(matrix))]
        reduced = _eliminate(sub, rhs)
        if reduced is None:
            continue
        work, pivots, sub_rank = reduced
        if sub_rank != len(columns):
            continue
        candidate = [F(0)] * n
        for row_index, local_col in pivots:
            candidate[columns[local_col]] = work[row_index][-1]
        if any(value < 0 for value in candidate):
            continue
        if any(sum(matrix[r][j] * candidate[j] for j in range(n)) != rhs[r]
               for r in range(len(matrix))):
            continue
        results.add(tuple(candidate))
    return list(results)


def reference_solve(flows, source_rows, target_rows, priors, source_totals,
                    controls):
    """Return exact optimum, one optimum, and per-flow optimal-face ranges."""
    n = len(flows)
    balance, rhs = [], []
    for row in source_rows:
        balance.append([F(row.get(k, 0)) for k in flows])
        rhs.append(F(source_totals[row["__id__"]]))
    for row in target_rows:
        if controls[row["__id__"]] is not None:
            balance.append([F(row.get(k, 0)) for k in flows])
            rhs.append(F(controls[row["__id__"]]))
    vertices = _basic_solutions(balance, rhs, n) if balance else [
        tuple(F(0) for _ in flows)]
    if not vertices:
        raise ReferenceInfeasible()

    best, optimal_points = None, []
    unit = [[F(1) if j == k else F(0) for j in range(n)] for k in range(n)]
    for mask in range(1 << n):
        matrix = [row[:] for row in balance]
        region_rhs = rhs[:]
        for k in range(n):
            if mask & (1 << k):
                matrix.append(unit[k])
                region_rhs.append(F(priors[flows[k]]))
        for point in _basic_solutions(matrix, region_rhs, n):
            cost = sum(abs(point[k] - priors[flows[k]]) for k in range(n))
            if best is None or cost < best:
                best, optimal_points = cost, [point]
            elif cost == best and point not in optimal_points:
                optimal_points.append(point)
    if best is None:
        raise ReferenceInfeasible()
    ranges = {}
    for j, key in enumerate(flows):
        values = [point[j] for point in optimal_points]
        ranges[key] = (min(values), max(values))
    return {"optimum": best,
            "allocation": dict(zip(flows, optimal_points[0])),
            "ranges": ranges}

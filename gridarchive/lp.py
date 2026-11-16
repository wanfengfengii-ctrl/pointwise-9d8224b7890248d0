"""Exact two-phase simplex over Fraction.

Standard-form linear program: minimize c.x subject to A x = b, x >= 0.
All arithmetic uses Fraction; no floating point tolerances exist anywhere.
Bland's rule (lowest-index entering column, lowest-index leaving basis) makes
termination finite in the presence of degeneracy.

Tableau convention. Every constraint row is canonical for the current basis
and stores its right-hand side in the final column. The objective row holds
reduced costs r_j = c_j - c_B A_B^-1 A_j on non-basic columns, zero on basic
columns, and minus the current objective value in the RHS. Row updates
subtract coefficient times the pivot row; a negative reduced cost therefore
marks an entering variable for minimization.
"""
from fractions import Fraction
from .errors import ValidationError


class LPInfeasible(Exception):
    """The equality system with non-negative variables has no solution."""


def _fraction(value):
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise ValidationError("linear program terms require integer or Fraction")
    return Fraction(value)


class Tableau:
    """Canonical tableau with an explicit basis."""

    def __init__(self, a, b, c):
        self.n = len(c)
        if any(len(row) != self.n for row in a) or len(a) != len(b):
            raise ValidationError("linear program matrix shape mismatch")
        normalized = []
        for row, rhs in zip(a, b):
            row = [_fraction(v) for v in row]
            rhs = _fraction(rhs)
            if rhs < 0:
                row = [-v for v in row]
                rhs = -rhs
            normalized.append((row, rhs))
        self.m = len(normalized)
        # Artificial columns are appended only for phase I and dropped later.
        self.width = self.n + self.m
        self.rows = [row + [Fraction(0)] * self.m + [rhs]
                     for row, rhs in normalized]
        for i in range(self.m):
            self.rows[i][self.n + i] = Fraction(1)
        self.basis = [self.n + i for i in range(self.m)]
        self._initial_objective = c
        self.objective = self._phase_one_row()

    def _phase_one_row(self):
        # Phase I minimizes the sum of the artificial variables. Starting from
        # coefficient one on artificial columns, canonicalize by subtracting the
        # basic (artificial) rows, which yields minus the sum of all rows.
        row = [Fraction(0)] * (self.width + 1)
        for pivot in self.rows:
            for j in range(self.width + 1):
                row[j] -= pivot[j]
        return row

    def _canonicalize(self, row):
        for i, basic in enumerate(self.basis):
            coefficient = row[basic]
            if coefficient:
                pivot = self.rows[i]
                for j in range(self.width + 1):
                    row[j] -= coefficient * pivot[j]

    def _iterate(self, real_only):
        while True:
            entering = None
            limit = self.n if real_only else self.width
            for j in range(limit):
                if j not in self.basis and self.objective[j] < 0:
                    entering = j
                    break
            if entering is None:
                return
            leaving = None
            best = None
            for i in range(self.m):
                pivot = self.rows[i][entering]
                if pivot > 0:
                    ratio = self.rows[i][self.width] / pivot
                    if best is None or ratio < best or (
                            ratio == best and self.basis[i] < self.basis[leaving]):
                        best = ratio
                        leaving = i
            if leaving is None:
                raise ArithmeticError("linear program is unbounded")
            self._pivot(leaving, entering)

    def _pivot(self, leaving, entering):
        pivot_row = self.rows[leaving]
        pivot = pivot_row[entering]
        for j in range(self.width + 1):
            pivot_row[j] /= pivot
        for i, row in enumerate(self.rows):
            if i == leaving:
                continue
            coefficient = row[entering]
            if coefficient:
                for j in range(self.width + 1):
                    row[j] -= coefficient * pivot_row[j]
        coefficient = self.objective[entering]
        if coefficient:
            for j in range(self.width + 1):
                self.objective[j] -= coefficient * pivot_row[j]
        self.basis[leaving] = entering

    def _artificial_residual(self):
        total = Fraction(0)
        for i, basic in enumerate(self.basis):
            if basic >= self.n:
                total += self.rows[i][self.width]
        return total

    def phase_one(self):
        self._iterate(real_only=False)
        if self._artificial_residual() != 0:
            raise LPInfeasible("phase I found no feasible basis")
        # An artificial variable left basic at value zero marks a redundant
        # equality: pivot a real column in when one exists, else delete the row.
        keep = [True] * self.m
        for i, basic in enumerate(self.basis):
            if basic < self.n:
                continue
            pivot = None
            for j in range(self.n):
                if self.rows[i][j] != 0 and j not in self.basis:
                    pivot = j
                    break
            if pivot is None:
                keep[i] = False
            else:
                self._pivot(i, pivot)
        self.m = sum(keep)
        self.rows = [row for row, kept in zip(self.rows, keep) if kept]
        self.basis = [basic for basic, kept in zip(self.basis, keep) if kept]
        # Artificial columns are no longer needed; keep real columns plus RHS.
        self.rows = [row[: self.n] + [row[self.width]] for row in self.rows]
        self.width = self.n
        self.set_objective(self._initial_objective)

    def add_equality(self, coefficients, rhs):
        """Append an equality while preserving a feasible optimal-face basis."""
        if len(coefficients) != self.n:
            raise ValidationError("equality width mismatch")
        new_row = [_fraction(v) for v in coefficients]
        rhs = _fraction(rhs)
        if rhs < 0:
            new_row = [-v for v in new_row]
            rhs = -rhs
        # Make the new row canonical for the current basis before adding the
        # artificial unit column, so basic columns keep their zero coefficients.
        for i, basic in enumerate(self.basis):
            coefficient = new_row[basic]
            if coefficient:
                pivot = self.rows[i]
                for j in range(self.n):
                    new_row[j] -= coefficient * pivot[j]
                rhs -= coefficient * pivot[self.width]
        if not any(new_row):
            if rhs != 0:
                raise LPInfeasible("added equality contradicts the constraints")
            return
        if rhs < 0:
            new_row = [-v for v in new_row]
            rhs = -rhs
        artificial = self.n
        for existing in self.rows:
            existing.insert(self.width, Fraction(0))
        self.width += 1
        self.rows.append(new_row + [Fraction(1), rhs])
        self.m += 1
        self.basis.append(artificial)
        saved = self.objective[: self.n] + [self.objective[-1]]
        # Mini phase I: starting from coefficient one on the new artificial
        # column, canonicalize by subtracting the new artificial-basis row.
        self.objective = [Fraction(0)] * (self.width + 1)
        for j in range(self.width + 1):
            self.objective[j] -= self.rows[-1][j]
        self._iterate(real_only=True)
        # The artificial column is basic in exactly one row; its value is the
        # mini phase-I residual, independent of any row reordering on pivots.
        residual = Fraction(0)
        for i, basic in enumerate(self.basis):
            if basic == artificial:
                residual = self.rows[i][self.width]
                break
        if residual != 0:
            raise LPInfeasible("added equality cut off the feasible region")
        if self.basis[-1] >= self.n:
            pivot = None
            for j in range(self.n):
                if self.rows[-1][j] != 0 and j not in self.basis:
                    pivot = j
                    break
            if pivot is None:
                del self.rows[-1]
                del self.basis[-1]
                self.m -= 1
                self.width = self.n
                self.rows = [item[: self.n] + [item[-1]] for item in self.rows]
                self.objective = saved
                self._canonicalize(self.objective)
                return
            self._pivot(self.m - 1, pivot)
        self.rows = [item[: self.n] + [item[-1]] for item in self.rows]
        self.width = self.n
        self.objective = saved
        self._canonicalize(self.objective)

    def set_objective(self, c):
        if len(c) != self.n:
            raise ValidationError("objective width mismatch")
        self.objective = [_fraction(v) for v in c] + [Fraction(0)]
        self._canonicalize(self.objective)

    def minimize(self, c):
        self.set_objective(c)
        self._iterate(real_only=True)

    def phase_two(self):
        self._iterate(real_only=True)

    def solution(self):
        values = [Fraction(0)] * self.n
        for i, basic in enumerate(self.basis):
            values[basic] = self.rows[i][self.width]
        return values

    def objective_value(self):
        return -self.objective[self.width]


def solve(a, b, c):
    """Minimize c.x subject to A x = b, x >= 0; return (solution, optimum, tableau)."""
    tableau = Tableau(a, b, c)
    tableau.phase_one()
    tableau.phase_two()
    return tableau.solution(), tableau.objective_value(), tableau

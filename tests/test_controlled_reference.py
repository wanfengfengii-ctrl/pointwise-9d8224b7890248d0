"""Property tests cross-checking the production solver against an independent
exact reference (tests/controlled_reference.py) that never imports the
production optimizer. Geometry is small and deterministic so the run is fast.
"""
import random
from fractions import Fraction as F
from gridarchive import Archive, Infeasible
from gridarchive.samples import rectangle
from .controlled_reference import ReferenceInfeasible, reference_solve
from .support import MemoryCase


def _random_case(archive, tag, rng):
    ns = rng.randint(1, 3)
    source_cells = {}
    for i in range(ns):
        source_cells["s%d" % i] = [
            rectangle(0, i, rng.randint(1, 3), i + 1)]
    max_width = max(rings[0][1][0] for rings in source_cells.values())
    nt = rng.randint(1, 3)
    cuts = sorted(rng.sample(range(1, max_width),
                             min(nt - 1, max(0, max_width - 1))))
    bounds = [0] + cuts + [max_width]
    target_cells = {
        "t%d" % j: [rectangle(bounds[j], 0, bounds[j + 1],
                              ns + rng.randint(0, 1))]
        for j in range(len(bounds) - 1)}
    source = archive.publish_grid(tag + "-s", tag + "-s", source_cells)
    target = archive.publish_grid(tag + "-t", tag + "-t", target_cells)
    values = {cell: F(rng.randint(0, 6), rng.randint(1, 3))
              for cell in source_cells}
    supported = sum(values.values(), F(0))
    controls = {}
    for cell in target_cells:
        roll = rng.random()
        if roll < 0.35:
            controls[cell] = None
        elif roll < 0.85:
            controls[cell] = supported * F(rng.randint(0, 4), rng.randint(4, 9))
        else:
            controls[cell] = supported + F(rng.randint(1, 3))
    field = archive.put_field(tag + "-f", source, values)
    control = archive.put_field(tag + "-c", target, controls)
    return (dict(source=source, target=target, field=field, control=control),
            values, controls)


def _reference_inputs(archive, bindings, values):
    job = archive.create_job(
        "geometry-" + str(bindings["source"]), bindings["source"],
        bindings["target"], bindings["field"])
    geometry = archive.run_job(job)["result"]
    flows, priors = [], {}
    source_rows, target_rows = {}, {}
    for s, overlaps in geometry["overlap_area"].items():
        source_rows.setdefault(s, {"__id__": s})
        for t, area in overlaps.items():
            target_rows.setdefault(t, {"__id__": t})
            if area > 0:
                key = ("x", s, t)
                flows.append(key)
                source_rows[s][key] = 1
                target_rows[t][key] = 1
                priors[key] = values[s] * area / geometry["source_area"][s]
    for s in geometry["source_area"]:
        area = geometry["source_area"][s] - sum(
            geometry["overlap_area"][s].values(), F(0))
        if area > 0:
            key = ("u", s, None)
            flows.append(key)
            source_rows[s][key] = 1
            priors[key] = values[s] * area / geometry["source_area"][s]
    return flows, list(source_rows.values()), list(target_rows.values()), priors


class ControlledReferenceTests(MemoryCase):
    def _run_seed(self, seed, count):
        rng = random.Random(seed)
        feasible = infeasible = 0
        for i in range(count):
            tag = "seed%d-%d" % (seed, i)
            bindings, values, controls = _random_case(self.archive, tag, rng)
            flows, srows, trows, priors = _reference_inputs(
                self.archive, bindings, values)
            job = self.archive.create_controlled_job(tag, **bindings)
            try:
                result = self.archive.run_controlled_job(job)["result"]
                production_feasible = True
            except Infeasible:
                production_feasible = False
            try:
                reference = reference_solve(
                    flows, srows, trows, priors, values, controls)
                reference_feasible = True
            except ReferenceInfeasible:
                reference_feasible = False
            self.assertEqual(production_feasible, reference_feasible, tag)
            if not production_feasible:
                infeasible += 1
                continue
            feasible += 1
            self.assertEqual(result["cost"], reference["optimum"], tag)
            produced = {}
            for s, targets in result["allocation"]["transfers"].items():
                for t, value in targets.items():
                    if ("x", s, t) in flows:
                        produced[("x", s, t)] = value
            for s, value in result["allocation"]["uncovered"].items():
                if ("u", s, None) in flows:
                    produced[("u", s, None)] = value
            # Source conservation and target controls hold exactly.
            for row in srows:
                self.assertEqual(
                    sum(produced.get(k, F(0)) * coef
                        for k, coef in row.items() if k != "__id__"),
                    values[row["__id__"]], tag)
            for row in trows:
                if controls[row["__id__"]] is not None:
                    self.assertEqual(
                        sum(produced.get(k, F(0)) * coef
                            for k, coef in row.items() if k != "__id__"),
                        controls[row["__id__"]], tag)
            # Exact ranges plus witnesses that attain each endpoint optimally.
            for key in flows:
                if key[0] == "x":
                    entry = result["ranges"]["transfers"][key[1]][key[2]]
                else:
                    entry = result["ranges"]["uncovered"][key[1]]
                self.assertEqual(
                    (entry["min"], entry["max"]), reference["ranges"][key],
                    (tag, key))
                for label, witness in (
                        ("min", entry["min_witness"]),
                        ("max", entry["max_witness"])):
                    wflows = {}
                    for s, targets in witness["transfers"].items():
                        for t, value in targets.items():
                            if ("x", s, t) in flows:
                                wflows[("x", s, t)] = value
                    for s, value in witness["uncovered"].items():
                        if ("u", s, None) in flows:
                            wflows[("u", s, None)] = value
                    self.assertTrue(all(v >= 0 for v in wflows.values()))
                    self.assertEqual(wflows[key], entry[label], (tag, key))
                    self.assertEqual(
                        sum(abs(wflows[k] - priors[k]) for k in flows),
                        reference["optimum"], tag)
        return feasible, infeasible

    def test_seed_20261116(self):
        feasible, infeasible = self._run_seed(20261116, 24)
        self.assertGreater(feasible, 0)
        self.assertGreater(infeasible, 0)

    def test_seed_99017(self):
        feasible, infeasible = self._run_seed(99017, 16)
        self.assertGreater(feasible, 0)
        self.assertGreater(infeasible, 0)

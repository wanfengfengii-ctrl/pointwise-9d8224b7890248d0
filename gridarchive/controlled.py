"""Controlled conservative remapping.

A controlled job freezes four identities: source grid, target grid, source
observation and target control observation. Allowed flows are decided by exact
positive-area support only; areas never act as capacities. The jointly
conservation- and control-satisfying allocation minimizes the L1 deviation from
the complete-area prior, and the report gives the exact optimal range of every
allowed flow with a complete optimal witness at each endpoint.
"""
import json
from fractions import Fraction as F
from .codec import dump, identity, name, pack, unpack
from .errors import Conflict, Infeasible, NotFound, ValidationError
from .fields import read_field
from .grids import read_grid, regions
from .lp import LPInfeasible, solve


def create_controlled_job(store, job_name, source, target, field, control):
    name(job_name)
    read_grid(store, source)
    read_grid(store, target)
    observation = read_field(store, field)
    controls = read_field(store, control)
    if observation["grid"] != source:
        raise ValidationError("field belongs to a different grid revision")
    if controls["grid"] != target:
        raise ValidationError("control belongs to a different grid revision")
    for cell, value in observation["values"].items():
        if value is None:
            raise ValidationError("controlled source observation has a missing value: " + cell)
        if value < 0:
            raise ValidationError("controlled source observation must be non-negative: " + cell)
    for cell, value in controls["values"].items():
        if value is not None and value < 0:
            raise ValidationError("target control must be non-negative or None: " + cell)
    with store.transaction("job") as db:
        prior = db.execute(
            "SELECT * FROM controlled_jobs WHERE name=?", (job_name,)).fetchone()
        if prior is not None:
            if (prior["source"], prior["target"], prior["field"],
                    prior["control"]) != (source, target, field, control):
                raise Conflict("controlled job name already bound")
            return prior["id"]
        job = db.execute(
            "INSERT INTO controlled_jobs(name,source,target,field,control)"
            " VALUES(?,?,?,?,?)",
            (job_name, source, target, field, control)).lastrowid
    return job


def read_controlled_result(store, job):
    identity(job)
    row = store.db.execute(
        "SELECT j.*, r.body AS result_body FROM controlled_jobs j"
        " LEFT JOIN controlled_results r ON r.id=j.result WHERE j.id=?",
        (job,)).fetchone()
    if row is None:
        raise NotFound("controlled job")
    return {"job": {"id": row["id"], "name": row["name"],
                    "source": row["source"], "target": row["target"],
                    "field": row["field"], "control": row["control"]},
            "result_id": row["result"],
            "result": None if row["result_body"] is None
            else unpack(json.loads(row["result_body"]))}


def _geometry(store, binding):
    source_regions = regions(store, binding["source"])
    target_regions = regions(store, binding["target"])
    source_cells = sorted(source_regions)
    target_cells = sorted(target_regions)
    source_area = {}
    overlap_area = {}
    uncovered_area = {}
    support = {}
    outside = set()
    for s in source_cells:
        geometry = source_regions[s]
        area = geometry.area()
        source_area[s] = area
        overlaps = {t: geometry.intersection_area(target_regions[t])
                    for t in target_cells}
        overlap_area[s] = overlaps
        covered = sum(overlaps.values(), F(0))
        if covered > area:
            raise ArithmeticError("target grid violates disjoint interior invariant")
        uncovered_area[s] = area - covered
        support[s] = [t for t in target_cells if overlaps[t] > 0]
        if uncovered_area[s] > 0:
            outside.add(s)
    return source_cells, target_cells, source_area, overlap_area, uncovered_area, support, outside


def _build_model(source_cells, target_cells, source_area, overlap_area,
                 uncovered_area, support, outside, values, controls):
    # Flow variables, one per positive-area support edge, then uncovered flows.
    flow_index = {}
    flow_vars = []
    for s in source_cells:
        for t in support[s]:
            flow_index[(s, t)] = len(flow_vars)
            flow_vars.append(("transfer", s, t))
    uncovered_index = {}
    for s in sorted(outside):
        uncovered_index[s] = len(flow_vars) + len(uncovered_index)
        flow_vars.append(("outside", s, None))
    n_flow = len(flow_vars)
    # Each flow carries one deviation variable and two L1 slack columns.
    n = n_flow + n_flow + 2 * n_flow
    rows = []
    rhs = []

    def zero_row():
        return [F(0)] * n

    # Source conservation: every allowed flow out of a source equals its value.
    for s in source_cells:
        row = zero_row()
        for t in support[s]:
            row[flow_index[(s, t)]] = F(1)
        if s in uncovered_index:
            row[uncovered_index[s]] = F(1)
        rows.append(row)
        rhs.append(values[s])
    # Target controls: None means unconstrained, zero still binds exactly.
    for t in target_cells:
        target_value = controls[t]
        if target_value is None:
            continue
        row = zero_row()
        for s in source_cells:
            if (s, t) in flow_index:
                row[flow_index[(s, t)]] = F(1)
        rows.append(row)
        rhs.append(target_value)
    # Complete-area prior of every allowed flow.
    priors = {}
    for kind, s, t in flow_vars:
        if kind == "transfer":
            priors[(kind, s, t)] = values[s] * overlap_area[s][t] / source_area[s]
        else:
            priors[(kind, s, None)] = (
                values[s] * uncovered_area[s] / source_area[s])
    # Absolute deviation d_k = |x_k - p_k| via two non-negative slacks.
    for k, (kind, s, t) in enumerate(flow_vars):
        prior = priors[(kind, s, t)]
        base = 2 * n_flow + 2 * k
        # x - d + slack_hi = p
        row = zero_row()
        row[k] = F(1)
        row[n_flow + k] = F(-1)
        row[base] = F(1)
        rows.append(row)
        rhs.append(prior)
        # -x - d + slack_lo = -p (negative rhs is normalized by the tableau).
        row = zero_row()
        row[k] = F(-1)
        row[n_flow + k] = F(-1)
        row[base + 1] = F(1)
        rows.append(row)
        rhs.append(-prior)
    objective = [F(0)] * n
    for k in range(n_flow):
        objective[n_flow + k] = F(1)
    return rows, rhs, objective, flow_index, uncovered_index, priors, flow_vars


def _allocation_from_solution(solution, source_cells, target_cells,
                              flow_index, uncovered_index):
    transfers = {s: {t: F(0) for t in target_cells} for s in source_cells}
    uncovered = {s: F(0) for s in source_cells}
    for (s, t), k in flow_index.items():
        transfers[s][t] = solution[k]
    for s, k in uncovered_index.items():
        uncovered[s] = solution[k]
    return {"transfers": transfers, "uncovered": uncovered}


def run_controlled_job(store, job):
    binding = read_controlled_result(store, job)["job"]
    values = read_field(store, binding["field"])["values"]
    controls = read_field(store, binding["control"])["values"]
    (source_cells, target_cells, source_area_vals, overlap_area,
     uncovered_area, support, outside) = _geometry(store, binding)
    rows, rhs, objective, flow_index, uncovered_index, priors, flow_vars = (
        _build_model(source_cells, target_cells, source_area_vals, overlap_area,
                     uncovered_area, support, outside, values, controls))
    try:
        solution, optimum, tableau = solve(rows, rhs, objective)
    except LPInfeasible as exc:
        raise Infeasible("controlled remapping has no feasible allocation") from exc
    # Pin every subsequent solve to the same optimal deviation face.
    tableau.add_equality(objective, optimum)

    def endpoint(objective_vector):
        tableau.minimize(objective_vector)
        return tableau.solution()

    ranges_transfers = {}
    ranges_uncovered = {}
    for s in source_cells:
        per_target = {}
        for t in support[s]:
            k = flow_index[(s, t)]
            vector = [F(0)] * len(objective)
            vector[k] = F(1)
            minimum = endpoint(vector)
            vector[k] = F(-1)
            maximum = endpoint(vector)
            per_target[t] = {
                "min": minimum[k],
                "max": maximum[k],
                "min_witness": _allocation_from_solution(
                    minimum, source_cells, target_cells, flow_index,
                    uncovered_index),
                "max_witness": _allocation_from_solution(
                    maximum, source_cells, target_cells, flow_index,
                    uncovered_index),
            }
        ranges_transfers[s] = per_target
    for s in sorted(outside):
        k = uncovered_index[s]
        vector = [F(0)] * len(objective)
        vector[k] = F(1)
        minimum = endpoint(vector)
        vector[k] = F(-1)
        maximum = endpoint(vector)
        ranges_uncovered[s] = {
            "min": minimum[k],
            "max": maximum[k],
            "min_witness": _allocation_from_solution(
                minimum, source_cells, target_cells, flow_index,
                uncovered_index),
            "max_witness": _allocation_from_solution(
                maximum, source_cells, target_cells, flow_index,
                uncovered_index),
        }

    allocation = _allocation_from_solution(
        solution, source_cells, target_cells, flow_index, uncovered_index)
    prior_transfers = {s: {t: F(0) for t in target_cells} for s in source_cells}
    prior_uncovered = {s: F(0) for s in source_cells}
    for (s, t), k in flow_index.items():
        prior_transfers[s][t] = priors[("transfer", s, t)]
    for s in outside:
        prior_uncovered[s] = priors[("outside", s, None)]
    prior = {"transfers": prior_transfers, "uncovered": prior_uncovered}
    allocated = {t: F(0) for t in target_cells}
    for s in source_cells:
        for t in target_cells:
            allocated[t] += allocation["transfers"][s][t]
    result = {
        "source_area": source_area_vals,
        "overlap_area": overlap_area,
        "uncovered_area": uncovered_area,
        "prior": prior,
        "allocation": allocation,
        "allocated": allocated,
        "cost": optimum,
        "ranges": {"transfers": ranges_transfers, "uncovered": ranges_uncovered},
    }
    with store.transaction("result") as db:
        result_id = db.execute(
            "INSERT INTO controlled_results(job,body) VALUES(?,?)",
            (job, dump(pack(result)))).lastrowid
        store.hit("result.after_insert")
        db.execute("UPDATE controlled_jobs SET result=? WHERE id=?",
                   (result_id, job))
    return read_controlled_result(store, job)

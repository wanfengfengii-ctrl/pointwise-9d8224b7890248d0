from fractions import Fraction as F
from .codec import dump, pack
from .fields import read_field
from .grids import regions
from .jobs import read_result


def run_job(store, job):
    binding = read_result(store, job)["job"]
    source = regions(store, binding["source"])
    target = regions(store, binding["target"])
    values = read_field(store, binding["field"])["values"]
    result = {"allocated": {cell: F(0) for cell in sorted(target)},
              "source_area": {}, "overlap_area": {}, "transfers": {},
              "uncovered": {}, "missing_area": {}, "uncovered_missing_area": {}}
    for cell in sorted(source):
        geometry = source[cell]
        area = geometry.area()
        overlaps = {other: geometry.intersection_area(target[other])
                    for other in sorted(target)}
        covered = sum(overlaps.values(), F(0))
        if covered > area:
            raise ArithmeticError("target grid violates disjoint interior invariant")
        result["source_area"][cell] = area
        result["overlap_area"][cell] = overlaps
        if values[cell] is None:
            result["missing_area"][cell] = {other: value for other, value in overlaps.items() if value}
            result["uncovered_missing_area"][cell] = area - covered
        else:
            transfers = {other: values[cell] * overlap / area
                         for other, overlap in overlaps.items()}
            result["transfers"][cell] = transfers
            result["uncovered"][cell] = values[cell] * (area - covered) / area
            for other, value in transfers.items():
                result["allocated"][other] += value
    with store.transaction("result") as db:
        result_id = db.execute("INSERT INTO results(job,body) VALUES(?,?)",
                               (job, dump(pack(result)))).lastrowid
        store.hit("result.after_insert")
        db.execute("UPDATE jobs SET result=? WHERE id=?", (result_id, job))
    return read_result(store, job)

"""Public input fixtures and hand-calculated expectations for controlled remapping.

Only existing Archive methods are used here. This module publishes no controlled
task and contains no transportation optimizer. Running it checks the supplied
geometry/observations and displays the ordinary area-only results.
"""
import json
from fractions import Fraction as F
from gridarchive import Archive
from gridarchive.codec import pack
from gridarchive.samples import rectangle


def _inputs(archive, prefix, sources, targets, values, controls):
    source = archive.publish_grid(prefix + "-source", prefix + "-source", sources)
    target = archive.publish_grid(prefix + "-target", prefix + "-target", targets)
    field = archive.put_field(prefix + "-field", source, values)
    control = archive.put_field(prefix + "-control", target, controls)
    return {"source": source, "target": target, "field": field, "control": control}


def ambiguous(archive, prefix="ambiguous"):
    return _inputs(
        archive, prefix,
        {"s1": [rectangle(0, 0, 4, 1)], "s2": [rectangle(0, 1, 4, 2)]},
        {"t1": [rectangle(0, 0, 3, 2)], "t2": [rectangle(3, 0, 4, 2)]},
        {"s1": 4, "s2": 4}, {"t1": 4, "t2": 4})


def unsupported(archive, prefix="unsupported"):
    return _inputs(
        archive, prefix,
        {"s1": [rectangle(0, 0, 1, 1)], "s2": [rectangle(2, 0, 3, 1)]},
        {"t1": [rectangle(0, 0, 1, 1)], "t2": [rectangle(2, 0, 3, 1)]},
        {"s1": 4, "s2": 4}, {"t1": 3, "t2": 5})


def free_and_outside(archive, prefix="free"):
    return _inputs(
        archive, prefix, {"s": [rectangle(0, 0, 3, 1)]},
        {"a": [rectangle(0, 0, 1, 1)], "b": [rectangle(1, 0, 2, 1)]},
        {"s": 3}, {"a": 2, "b": None})


def zero_and_touch(archive, prefix="zero"):
    return _inputs(
        archive, prefix, {"s": [rectangle(0, 0, 2, 1)]},
        {"left": [rectangle(0, 0, 1, 1)],
         "right": [rectangle(1, 0, 2, 1)],
         "touch": [rectangle(2, 0, 3, 1)]},
        {"s": "1/3"}, {"left": 0, "right": None, "touch": 0})


EXPECTED = {
    "ambiguous": {
        "cost": F(4),
        "target_totals": {"t1": F(4), "t2": F(4)},
        "flow_ranges": {"s1/t1": [F(1), F(3)], "s1/t2": [F(1), F(3)],
                        "s2/t1": [F(1), F(3)], "s2/t2": [F(1), F(3)]},
    },
    "unsupported": {"outcome": "Infeasible"},
    "free": {
        "cost": F(2), "flow_ranges": {"s/a": [F(2), F(2)],
                                     "s/b": [F(0), F(1)],
                                     "s/outside": [F(0), F(1)]},
    },
    "zero": {
        "cost": F(1, 3),
        "target_totals": {"left": F(0), "right": F(1, 3), "touch": F(0)},
        "flow_ranges": {"s/left": [F(0), F(0)], "s/right": [F(1, 3), F(1, 3)]},
    },
}
# Slash-separated names in EXPECTED are explanatory labels, not API keys.
# Actual result dictionaries always retain source and target strings separately.


def main():
    report = {}
    for label, build in (
        ("ambiguous", ambiguous), ("unsupported", unsupported),
        ("free", free_and_outside), ("zero", zero_and_touch),
    ):
        with Archive() as archive:
            bindings = build(archive)
            job = archive.create_job(
                label + "-ordinary", bindings["source"], bindings["target"], bindings["field"])
            result = archive.run_job(job)["result"]
            if label == "ambiguous":
                assert result["source_area"] == {"s1": F(4), "s2": F(4)}
                assert result["overlap_area"] == {
                    "s1": {"t1": F(3), "t2": F(1)}, "s2": {"t1": F(3), "t2": F(1)}}
                assert result["allocated"] == {"t1": F(6), "t2": F(2)}
            elif label == "unsupported":
                assert result["overlap_area"] == {
                    "s1": {"t1": F(1), "t2": F(0)}, "s2": {"t1": F(0), "t2": F(1)}}
                assert result["allocated"] == {"t1": F(4), "t2": F(4)}
            elif label == "free":
                assert result["allocated"] == {"a": F(1), "b": F(1)}
                assert result["uncovered"] == {"s": F(1)}
            else:
                assert result["allocated"] == {"left": F(1, 6), "right": F(1, 6), "touch": F(0)}
                assert result["uncovered"] == {"s": F(0)}
            report[label] = {
                "bindings": bindings,
                "source_values": archive.read_field(bindings["field"])["values"],
                "controls": archive.read_field(bindings["control"])["values"],
                "ordinary_area_result": result,
                "controlled_expectation": EXPECTED[label],
            }
    print(json.dumps(pack(report), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

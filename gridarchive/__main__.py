import argparse
import json
import tempfile
from fractions import Fraction as F
from pathlib import Path
from . import Archive, Infeasible
from .codec import pack
from .samples import build_legacy, rectangle
import controlled_examples


def _controlled_demo(path):
    """Publish, run and re-verify a controlled job against a real on-disk DB."""
    with Archive(path) as archive:
        bindings = controlled_examples.ambiguous(archive, "demo")
        job = archive.create_controlled_job("demo-controlled", **bindings)
        first = archive.run_controlled_job(job)
        result = first["result"]
        assert result["cost"] == F(4)
        assert result["allocated"] == {"t1": F(4), "t2": F(4)}
        entry = result["ranges"]["transfers"]["s1"]["t1"]
        assert (entry["min"], entry["max"]) == (F(1), F(3))
        # The two independent endpoints cannot be merged into one joint flow.
        assert sum(result["ranges"]["transfers"][s]["t1"]["max"]
                   for s in ("s1", "s2")) == F(6)
        # A mathematically impossible task is created but never published.
        impossible = controlled_examples.unsupported(archive, "demo-unsup")
        bad_job = archive.create_controlled_job("demo-unsup-job", **impossible)
        try:
            archive.run_controlled_job(bad_job)
            raise AssertionError("infeasible task unexpectedly solved")
        except Infeasible:
            pass
        assert archive.read_controlled_result(bad_job)["result"] is None
        # Publish a same-named replacement grid and a fresh control observation;
        # the frozen controlled job must keep its original four identities.
        replacement = archive.publish_grid("demo-source", "demo-source-v2", {
            "s1": [rectangle(0, 0, 4, 1)], "s2": [rectangle(0, 1, 4, 2)]})
        new_control = archive.put_field(
            "demo-control-v2", bindings["target"], {"t1": 5, "t2": 3})
        first_id = first["result_id"]
    with Archive(path) as archive:
        assert archive.head("demo-source") == replacement
        assert archive.read_field(new_control)["values"] == {"t1": F(5), "t2": F(3)}
        rerun = archive.run_controlled_job(job)
        assert rerun["result"] == result
        assert rerun["result_id"] != first_id
        assert archive.read_controlled_result(job)["result_id"] == rerun["result_id"]
        assert archive.read_controlled_result(job)["job"] == first["job"]
        assert archive.read_controlled_result(bad_job)["result"] is None
    return first, rerun


def main():
    parser = argparse.ArgumentParser(description="Exact conservative grid archive")
    parser.add_argument("command", choices=["demo"])
    parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gridarchive-demo-") as directory:
        path = str(Path(directory) / "archive.sqlite")
        ids = build_legacy(path)
        with Archive(path) as archive:
            original = archive.read_result(ids["job"])
            rerun = archive.run_job(ids["job"])
            assert original["result"] == rerun["result"]
            assert rerun["result"]["allocated"]["small"] == 3
            assert rerun["result"]["allocated"]["large"] == 9
            assert archive.head("source") == ids["new_source"]
            legacy = {
                "bindings": ids,
                "historical": rerun,
                "current": archive.read_result(ids["new_job"]),
                "self_crossing": archive.read_result(ids["bow_job"]),
                "source_head": archive.head("source"),
            }
        controlled_first, controlled_rerun = _controlled_demo(path)
        print(json.dumps(pack({
            "legacy": legacy,
            "controlled_first": controlled_first,
            "controlled_rerun": controlled_rerun,
        }), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Runnable end-to-end check of the controlled remapping delivery.

Exercises, against a real on-disk SQLite archive and with assertions on real
business results (not printed success messages):

  * saving a controlled task and executing its multi-solution allocation;
  * infeasible support rejected without publishing any result;
  * same-named grid/control replacement leaving the frozen binding untouched;
  * reopen, rerun identity of values and movement of the result pointer;
  * rollback at both result hooks and at the job-creation hook;
  * the hand-calculated expectations from controlled_examples.EXPECTED.

Run:  python3.11 -B -m verify_controlled
"""
import tempfile
from fractions import Fraction as F
from pathlib import Path

from gridarchive import Archive, Infeasible
import controlled_examples


class Boom(RuntimeError):
    def __init__(self, event):
        super().__init__(event)
        self.event = event


def _fault(event):
    def hook(actual):
        if actual == event:
            raise Boom(event)
    return hook


def _check_examples(archive):
    bindings = controlled_examples.ambiguous(archive, "verify-amb")
    job = archive.create_controlled_job("verify-amb", **bindings)
    result = archive.run_controlled_job(job)["result"]
    expected = controlled_examples.EXPECTED["ambiguous"]
    assert result["cost"] == expected["cost"]
    for label, (minimum, maximum) in expected["flow_ranges"].items():
        s, t = label.split("/")
        entry = result["ranges"]["transfers"][s][t]
        assert (entry["min"], entry["max"]) == (minimum, maximum)
    assert result["allocated"] == expected["target_totals"]

    unsupported = controlled_examples.unsupported(archive, "verify-unsup")
    bad = archive.create_controlled_job("verify-unsup", **unsupported)
    try:
        archive.run_controlled_job(bad)
        raise AssertionError("unsupported task must be infeasible")
    except Infeasible:
        pass
    assert archive.read_controlled_result(bad)["result"] is None

    free_bindings = controlled_examples.free_and_outside(archive, "verify-free")
    free_job = archive.create_controlled_job("verify-free", **free_bindings)
    free = archive.run_controlled_job(free_job)["result"]
    assert free["cost"] == controlled_examples.EXPECTED["free"]["cost"]
    assert (free["ranges"]["transfers"]["s"]["b"]["min"],
            free["ranges"]["transfers"]["s"]["b"]["max"]) == (F(0), F(1))

    zero_bindings = controlled_examples.zero_and_touch(archive, "verify-zero")
    zero_job = archive.create_controlled_job("verify-zero", **zero_bindings)
    zero = archive.run_controlled_job(zero_job)["result"]
    assert zero["cost"] == controlled_examples.EXPECTED["zero"]["cost"]
    assert zero["allocated"] == controlled_examples.EXPECTED["zero"]["target_totals"]
    return bindings, job, result


def main():
    with tempfile.TemporaryDirectory(prefix="verify-controlled-") as directory:
        path = str(Path(directory) / "archive.sqlite")
        archive = Archive(path)
        bindings, job, result = _check_examples(archive)
        first_id = archive.read_controlled_result(job)["result_id"]

        # Faults at both result hooks during a first run leave no candidate.
        for event in ("result.after_insert", "result.before_commit"):
            probe_bindings = controlled_examples.free_and_outside(
                archive, "probe-" + event)
            probe = archive.create_controlled_job(
                "probe-" + event, **probe_bindings)
            archive.close()
            archive = Archive(path, fault=_fault(event))
            try:
                archive.run_controlled_job(probe)
                raise AssertionError(event + " did not fire")
            except Boom:
                pass
            archive.close()
            archive = Archive(path)
            assert archive.read_controlled_result(probe)["result"] is None
        # A failed rerun preserves the previously published complete result.
        archive.close()
        archive = Archive(path, fault=_fault("result.before_commit"))
        try:
            archive.run_controlled_job(job)
            raise AssertionError("rerun fault did not fire")
        except Boom:
            pass
        archive.close()
        archive = Archive(path)
        assert archive.read_controlled_result(job)["result"] == result
        # A job-creation fault adds no controlled job.
        before = archive._store.db.execute(
            "SELECT COUNT(*) FROM controlled_jobs").fetchone()[0]
        archive.close()
        archive = Archive(path, fault=_fault("job.before_commit"))
        try:
            archive.create_controlled_job("rolled-back", **bindings)
            raise AssertionError("job fault did not fire")
        except Boom:
            pass
        archive.close()
        archive = Archive(path)
        assert archive._store.db.execute(
            "SELECT COUNT(*) FROM controlled_jobs").fetchone()[0] == before
        # Replacement does not move the frozen binding; reopen reruns identically.
        replacement = archive.publish_grid("verify-amb-source", "verify-amb-v2", {
            "s1": [controlled_examples.rectangle(0, 0, 4, 1)],
            "s2": [controlled_examples.rectangle(0, 1, 4, 2)]})
        archive.put_field("verify-amb-control-v2", bindings["target"],
                          {"t1": 5, "t2": 3})
        archive.close()
        archive = Archive(path)
        assert archive.head("verify-amb-source") == replacement
        rerun = archive.run_controlled_job(job)
        assert rerun["result"] == result
        assert rerun["result_id"] != first_id
        assert archive.read_controlled_result(job)["result_id"] == rerun["result_id"]
        assert archive.read_controlled_result(job)["job"]["source"] == bindings["source"]
        archive.close()
    print("verify_controlled: save, execute, replace, failure and reopen OK")


if __name__ == "__main__":
    main()

from fractions import Fraction as F
from gridarchive import (Archive, Conflict, Infeasible, NotFound,
                         ValidationError)
from gridarchive.samples import rectangle
from .support import DiskCase, MemoryCase, counts


def _ambiguous(archive, prefix="amb"):
    source = archive.publish_grid(prefix + "-s", prefix + "-s", {
        "s1": [rectangle(0, 0, 4, 1)], "s2": [rectangle(0, 1, 4, 2)]})
    target = archive.publish_grid(prefix + "-t", prefix + "-t", {
        "t1": [rectangle(0, 0, 3, 2)], "t2": [rectangle(3, 0, 4, 2)]})
    field = archive.put_field(prefix + "-f", source, {"s1": 4, "s2": 4})
    control = archive.put_field(prefix + "-c", target, {"t1": 4, "t2": 4})
    return source, target, field, control


def _assert_witness(test, witness, source_cells, target_cells, values,
                    controls, cost, priors):
    for s in source_cells:
        total = sum(witness["transfers"][s].values(), F(0)) + witness["uncovered"][s]
        test.assertEqual(total, values[s])
    for t in target_cells:
        if controls[t] is not None:
            test.assertEqual(
                sum(witness["transfers"][s][t] for s in source_cells), controls[t])
    observed = sum(
        abs(witness["transfers"][s][t] - priors["transfers"][s][t])
        for s in source_cells for t in target_cells)
    observed += sum(abs(witness["uncovered"][s] - priors["uncovered"][s])
                    for s in source_cells)
    test.assertEqual(observed, cost)


class ControlledExampleTests(MemoryCase):
    def test_ambiguous_ranges_and_complete_witnesses(self):
        source, target, field, control = _ambiguous(self.archive)
        job = self.archive.create_controlled_job(
            "controlled", source, target, field, control)
        result = self.archive.run_controlled_job(job)["result"]
        self.assertEqual(result["cost"], F(4))
        self.assertEqual(result["allocated"], {"t1": F(4), "t2": F(4)})
        values = self.archive.read_field(field)["values"]
        controls = self.archive.read_field(control)["values"]
        for s in ("s1", "s2"):
            self.assertEqual(set(result["ranges"]["transfers"][s]), {"t1", "t2"})
            for t in ("t1", "t2"):
                entry = result["ranges"]["transfers"][s][t]
                self.assertEqual((entry["min"], entry["max"]), (F(1), F(3)))
                self.assertNotIn("touch", entry["min_witness"]["transfers"][s])
                for witness in (entry["min_witness"], entry["max_witness"]):
                    _assert_witness(self, witness, ("s1", "s2"), ("t1", "t2"),
                                    values, controls, result["cost"], result["prior"])
        self.assertEqual(result["ranges"]["uncovered"], {})
        # Independent endpoints must not be combinable into one joint solution.
        joined = sum(
            result["ranges"]["transfers"][s]["t1"]["max"] for s in ("s1", "s2"))
        self.assertEqual(joined, F(6))

    def test_unsupported_is_rejected_without_publishing(self):
        source = self.archive.publish_grid("us", "us", {
            "s1": [rectangle(0, 0, 1, 1)], "s2": [rectangle(2, 0, 3, 1)]})
        target = self.archive.publish_grid("ut", "ut", {
            "t1": [rectangle(0, 0, 1, 1)], "t2": [rectangle(2, 0, 3, 1)]})
        field = self.archive.put_field("uf", source, {"s1": 4, "s2": 4})
        control = self.archive.put_field("uc", target, {"t1": 3, "t2": 5})
        job = self.archive.create_controlled_job(
            "unsupported", source, target, field, control)
        with self.assertRaises(Infeasible):
            self.archive.run_controlled_job(job)
        self.assertIsNone(self.archive.read_controlled_result(job)["result"])
        self.assertIsNone(self.archive.read_controlled_result(job)["result_id"])
        with self.assertRaises(Infeasible):
            self.archive.run_controlled_job(job)

    def test_free_target_and_uncovered_exit_ranges(self):
        source = self.archive.publish_grid("fs", "fs", {"s": [rectangle(0, 0, 3, 1)]})
        target = self.archive.publish_grid("ft", "ft", {
            "a": [rectangle(0, 0, 1, 1)], "b": [rectangle(1, 0, 2, 1)]})
        field = self.archive.put_field("ff", source, {"s": 3})
        control = self.archive.put_field("fc", target, {"a": 2, "b": None})
        job = self.archive.create_controlled_job("free", source, target, field, control)
        result = self.archive.run_controlled_job(job)["result"]
        self.assertEqual(result["cost"], F(2))
        self.assertEqual(result["allocated"]["a"], F(2))
        self.assertEqual(result["uncovered_area"]["s"], F(1))
        self.assertEqual(
            (result["ranges"]["transfers"]["s"]["a"]["min"],
             result["ranges"]["transfers"]["s"]["a"]["max"]), (F(2), F(2)))
        self.assertEqual(
            (result["ranges"]["transfers"]["s"]["b"]["min"],
             result["ranges"]["transfers"]["s"]["b"]["max"]), (F(0), F(1)))
        uncovered = result["ranges"]["uncovered"]["s"]
        self.assertEqual((uncovered["min"], uncovered["max"]), (F(0), F(1)))
        for entry in (result["ranges"]["transfers"]["s"]["a"],
                      result["ranges"]["transfers"]["s"]["b"], uncovered):
            for witness in (entry["min_witness"], entry["max_witness"]):
                self.assertEqual(
                    sum(witness["transfers"]["s"].values(), F(0))
                    + witness["uncovered"]["s"], F(3))

    def test_zero_control_touch_support_and_rational_value(self):
        source = self.archive.publish_grid("zs", "zs", {"s": [rectangle(0, 0, 2, 1)]})
        target = self.archive.publish_grid("zt", "zt", {
            "left": [rectangle(0, 0, 1, 1)], "right": [rectangle(1, 0, 2, 1)],
            "touch": [rectangle(2, 0, 3, 1)]})
        field = self.archive.put_field("zf", source, {"s": "1/3"})
        control = self.archive.put_field(
            "zc", target, {"left": 0, "right": None, "touch": 0})
        job = self.archive.create_controlled_job("zero", source, target, field, control)
        result = self.archive.run_controlled_job(job)["result"]
        self.assertEqual(result["cost"], F(1, 3))
        self.assertEqual(result["allocated"],
                         {"left": F(0), "right": F(1, 3), "touch": F(0)})
        self.assertEqual(set(result["ranges"]["transfers"]["s"]), {"left", "right"})
        left = result["ranges"]["transfers"]["s"]["left"]
        right = result["ranges"]["transfers"]["s"]["right"]
        self.assertEqual((left["min"], left["max"]), (F(0), F(0)))
        self.assertEqual((right["min"], right["max"]), (F(1, 3), F(1, 3)))
        self.assertEqual(result["ranges"]["uncovered"], {})
        self.assertEqual(result["allocation"]["transfers"]["s"]["touch"], F(0))

    def test_all_zero_sources_report_zero_ranges_on_support(self):
        source = self.archive.publish_grid("q", "q", {"s": [rectangle(0, 0, 2, 1)]})
        target = self.archive.publish_grid("r", "r", {
            "t1": [rectangle(0, 0, 1, 1)], "t2": [rectangle(1, 0, 2, 1)]})
        field = self.archive.put_field("qf", source, {"s": 0})
        control = self.archive.put_field("qc", target, {"t1": 0, "t2": None})
        job = self.archive.create_controlled_job("zeros", source, target, field, control)
        result = self.archive.run_controlled_job(job)["result"]
        self.assertEqual(result["cost"], F(0))
        for t in ("t1", "t2"):
            entry = result["ranges"]["transfers"]["s"][t]
            self.assertEqual((entry["min"], entry["max"]), (F(0), F(0)))
        self.assertEqual(result["allocated"], {"t1": F(0), "t2": F(0)})

    def test_structure_uses_original_keys_and_no_shared_memory(self):
        source, target, field, control = _ambiguous(self.archive)
        job = self.archive.create_controlled_job("structured", source, target, field, control)
        result = self.archive.run_controlled_job(job)["result"]
        self.assertEqual(set(result["source_area"]), {"s1", "s2"})
        self.assertEqual(set(result["overlap_area"]["s1"]), {"t1", "t2"})
        self.assertEqual(set(result["prior"]["transfers"]["s1"]), {"t1", "t2"})
        self.assertEqual(set(result["allocation"]["transfers"]["s2"]), {"t1", "t2"})
        result["allocation"]["transfers"]["s1"]["t1"] = F(999)
        reread = self.archive.read_controlled_result(job)["result"]
        self.assertNotEqual(reread["allocation"]["transfers"]["s1"]["t1"], F(999))


class ControlledValidationTests(MemoryCase):
    def _bindings(self):
        source = self.archive.publish_grid("s", "s", {"s": [rectangle(0, 0, 1, 1)]})
        target = self.archive.publish_grid("t", "t", {"t": [rectangle(0, 0, 1, 1)]})
        return source, target

    def test_negative_missing_and_misbound_inputs_rejected(self):
        source, target = self._bindings()
        negative = self.archive.put_field("fn", source, {"s": -1})
        missing = self.archive.put_field("fm", source, {"s": None})
        good = self.archive.put_field("fg", source, {"s": 1})
        bad_control = self.archive.put_field("cn", target, {"t": -1})
        null_control = self.archive.put_field("c0", target, {"t": None})
        good_control = self.archive.put_field("cg", target, {"t": 1})
        before = counts(self.archive)
        for kwargs in (
            dict(name="a", source=source, target=target, field=negative, control=good_control),
            dict(name="b", source=source, target=target, field=missing, control=good_control),
            dict(name="c", source=source, target=target, field=good, control=bad_control),
            dict(name="d", source=target, target=target, field=good, control=good_control),
            dict(name="e", source=source, target=source, field=good, control=null_control),
        ):
            with self.assertRaises(ValidationError):
                self.archive.create_controlled_job(**kwargs)
        self.assertEqual(counts(self.archive), before)

    def test_unknown_references_and_bad_identity(self):
        source, target = self._bindings()
        field = self.archive.put_field("f", source, {"s": 1})
        control = self.archive.put_field("c", target, {"t": 1})
        with self.assertRaises(NotFound):
            self.archive.create_controlled_job("u", source, target, field, 999)
        with self.assertRaises(NotFound):
            self.archive.run_controlled_job(999)
        with self.assertRaises(ValidationError):
            self.archive.read_controlled_result(0)
        with self.assertRaises(NotFound):
            self.archive.read_controlled_result(999)

    def test_name_replay_conflict_and_separate_namespace(self):
        source, target = self._bindings()
        field = self.archive.put_field("f", source, {"s": 1})
        control = self.archive.put_field("c", target, {"t": 1})
        job = self.archive.create_controlled_job("same", source, target, field, control)
        self.assertEqual(
            self.archive.create_controlled_job("same", source, target, field, control), job)
        replacement = self.archive.publish_grid("s2", "s2", {"s": [rectangle(0, 0, 1, 1)]})
        replacement_field = self.archive.put_field("f2", replacement, {"s": 1})
        with self.assertRaises(Conflict):
            self.archive.create_controlled_job(
                "same", replacement, target, replacement_field, control)
        ordinary = self.archive.create_job("same", source, target, field)
        self.assertEqual(self.archive.read_result(ordinary)["job"]["name"], "same")
        self.assertEqual(
            self.archive.read_controlled_result(job)["job"]["name"], "same")


class ControlledPersistenceTests(DiskCase):
    def test_reopen_replacement_rerun_and_faults_preserve_results(self):
        source, target, field, control = _ambiguous(self.archive, "disk")
        job = self.archive.create_controlled_job(
            "frozen", source, target, field, control)
        first = self.archive.run_controlled_job(job)
        self.assertEqual(first["result_id"], 1)

        class Boom(RuntimeError):
            def __init__(self, event):
                self.event = event

        for event in ("result.after_insert", "result.before_commit"):
            other_source = self.archive.publish_grid(
                event + "-s", event + "-s", {"s": [rectangle(0, 0, 1, 1)]})
            other_target = self.archive.publish_grid(
                event + "-t", event + "-t", {"t": [rectangle(0, 0, 1, 1)]})
            other_field = self.archive.put_field(
                event + "-f", other_source, {"s": 1})
            other_control = self.archive.put_field(
                event + "-c", other_target, {"t": None})
            other_job = self.archive.create_controlled_job(
                event, other_source, other_target, other_field, other_control)
            self.reopen(fault=lambda actual, e=event: (_ for _ in ()).throw(Boom(e))
                        if actual == e else None)
            with self.assertRaises(Boom):
                self.archive.run_controlled_job(other_job)
            self.reopen()
            self.assertIsNone(self.archive.read_controlled_result(other_job)["result"])
        # A failed rerun keeps the previously published complete result.
        result_count = self.archive._store.db.execute(
            "SELECT COUNT(*) FROM controlled_results").fetchone()[0]
        self.reopen(fault=lambda actual: (_ for _ in ()).throw(Boom(actual))
                    if actual == "result.before_commit" else None)
        with self.assertRaises(Boom):
            self.archive.run_controlled_job(job)
        self.reopen()
        self.assertEqual(self.archive.read_controlled_result(job), first)
        self.assertEqual(self.archive._store.db.execute(
            "SELECT COUNT(*) FROM controlled_results").fetchone()[0], result_count)
        # Job creation fault adds no controlled job.
        before = self.archive._store.db.execute(
            "SELECT COUNT(*) FROM controlled_jobs").fetchone()[0]
        self.reopen(fault=lambda actual: (_ for _ in ()).throw(Boom(actual))
                    if actual == "job.before_commit" else None)
        with self.assertRaises(Boom):
            self.archive.create_controlled_job("rolled-back", source, target, field, control)
        self.reopen()
        self.assertEqual(self.archive._store.db.execute(
            "SELECT COUNT(*) FROM controlled_jobs").fetchone()[0], before)
        # Replacing the same-named grid never moves the frozen binding.
        new_source = self.archive.publish_grid("disk-s", "disk-s-v2", {
            "s1": [rectangle(0, 0, 4, 1)], "s2": [rectangle(0, 1, 4, 2)]})
        self.assertEqual(self.archive.head("disk-s"), new_source)
        self.reopen()
        rerun = self.archive.run_controlled_job(job)
        self.assertEqual(rerun["result"], first["result"])
        self.assertNotEqual(rerun["result_id"], first["result_id"])
        self.assertEqual(self.archive.read_controlled_result(job)["result_id"],
                         rerun["result_id"])
        self.assertEqual(self.archive.read_controlled_result(job)["job"], first["job"])

    def test_legacy_archive_opens_with_old_data_and_behaviour(self):
        from gridarchive.samples import build_legacy
        self.archive.close()
        ids = build_legacy(self.path)
        self.archive = Archive(self.path)
        # Old ordinary jobs/results survive untouched alongside the new tables.
        self.assertEqual(
            self.archive.read_result(ids["job"])["result"]["allocated"]["small"], 3)
        self.assertEqual(self.archive._store.db.execute(
            "SELECT COUNT(*) FROM controlled_jobs").fetchone()[0], 0)
        self.assertEqual(self.archive._store.db.execute(
            "PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(list(self.archive._store.db.execute(
            "PRAGMA foreign_key_check")), [])

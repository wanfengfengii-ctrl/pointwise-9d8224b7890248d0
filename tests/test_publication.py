from gridarchive import NotFound
from .support import DiskCase, basic, counts, rectangle


class InjectedFailure(RuntimeError):
    pass


class PublicationTests(DiskCase):
    def arm(self, event):
        def fail(actual):
            if actual == event:
                raise InjectedFailure(event)
        return self.reopen(fault=fail)

    def test_first_result_failure_and_reopen_retry(self):
        _, _, _, job = basic(self.archive)
        before = counts(self.archive)
        for event in ("result.after_insert", "result.before_commit"):
            with self.subTest(event=event):
                self.arm(event)
                with self.assertRaises(InjectedFailure):
                    self.archive.run_job(job)
                self.assertEqual(counts(self.archive), before)
                self.assertIsNone(self.archive.read_result(job)["result"])
                self.reopen()
                self.assertIsNone(self.archive.read_result(job)["result"])
        result = self.archive.run_job(job)
        self.assertEqual(result["result"]["allocated"]["large"], 9)
        self.reopen()
        self.assertEqual(self.archive.read_result(job), result)

    def test_failed_rerun_preserves_previous_complete_result(self):
        _, _, _, job = basic(self.archive)
        original = self.archive.run_job(job)
        before = counts(self.archive)
        self.arm("result.before_commit")
        with self.assertRaises(InjectedFailure):
            self.archive.run_job(job)
        self.reopen()
        self.assertEqual(self.archive.read_result(job), original)
        self.assertEqual(counts(self.archive), before)
        self.assertEqual(self.archive.run_job(job)["result"], original["result"])

    def test_grid_field_and_job_publication_rollback(self):
        source, target, field, job = basic(self.archive)
        before = counts(self.archive)
        self.arm("grid.before_commit")
        with self.assertRaises(InjectedFailure):
            self.archive.publish_grid("source", "candidate", {"new": [rectangle(10, 0, 11, 1)]})
        self.reopen()
        self.assertEqual(self.archive.head("source"), source)
        with self.assertRaises(NotFound):
            self.archive.grid_receipt("candidate")
        self.assertEqual(counts(self.archive), before)
        self.arm("field.before_commit")
        with self.assertRaises(InjectedFailure):
            self.archive.put_field("candidate", source, {"mass": 5, "missing": 0, "zero": None})
        self.reopen()
        with self.assertRaises(NotFound):
            self.archive.field_receipt("candidate")
        self.assertEqual(counts(self.archive), before)
        self.arm("job.before_commit")
        with self.assertRaises(InjectedFailure):
            self.archive.create_job("candidate", source, target, field)
        self.reopen()
        self.assertEqual(counts(self.archive), before)
        self.assertEqual(self.archive.run_job(job)["result"]["allocated"]["small"], 3)

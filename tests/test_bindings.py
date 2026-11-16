from gridarchive import Archive, Conflict, NotFound, ValidationError
from .support import DiskCase, basic, counts, rectangle


class BindingTests(DiskCase):
    def test_replacement_preserves_history(self):
        source, target, field, job = basic(self.archive)
        old = self.archive.run_job(job)
        newer = self.archive.publish_grid("source", "source-2", {
            "new": [rectangle(0, 0, 1, 1)]})
        new_field = self.archive.put_field("field-2", newer, {"new": 20})
        new_job = self.archive.create_job("new", newer, target, new_field)
        self.assertEqual(self.archive.run_job(new_job)["result"]["allocated"]["small"], 20)
        target2 = self.archive.publish_grid("target", "target-2", {
            "away": [rectangle(100, 100, 101, 101)]})
        self.reopen()
        self.assertEqual(self.archive.run_job(job)["result"], old["result"])
        self.assertEqual(self.archive.read_result(job)["job"], old["job"])
        self.assertEqual(self.archive.head("source"), newer)
        self.assertEqual(self.archive.head("target"), target2)
        self.assertEqual(self.archive.create_job("bound", source, target, field), job)
        with self.assertRaises(Conflict):
            self.archive.create_job("bound", newer, target, new_field)

    def test_field_mismatch_and_unknown_references(self):
        source, target, field, job = basic(self.archive)
        before = counts(self.archive)
        with self.assertRaises(ValidationError):
            self.archive.create_job("bad", target, source, field)
        with self.assertRaises(NotFound):
            self.archive.create_job("bad", source, 999, field)
        self.assertEqual(counts(self.archive), before)
        self.assertIsNone(self.archive.read_result(job)["result"])
        self.assertIsNone(self.archive.read_result(job)["result_id"])
        for operation in (self.archive.read_grid, self.archive.read_field,
                          self.archive.read_result, self.archive.run_job):
            with self.assertRaises(NotFound):
                operation(999)
        with self.assertRaises(NotFound):
            self.archive.head("absent")

    def test_existing_objects_see_commits_without_rebinding(self):
        source, target, field, job = basic(self.archive)
        with Archive(self.path) as peer:
            self.assertIsNone(peer.read_result(job)["result"])
            result = self.archive.run_job(job)
            self.assertEqual(peer.read_result(job), result)
            new = self.archive.publish_grid("source", "new-source", {
                "new": [rectangle(10, 0, 11, 1)]})
            self.assertEqual(peer.head("source"), new)
            self.assertEqual(peer.read_result(job)["job"]["source"], source)
            self.assertEqual(peer.read_field(field)["grid"], source)

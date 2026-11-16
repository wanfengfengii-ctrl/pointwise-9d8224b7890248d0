from gridarchive import Archive
from gridarchive.samples import build_legacy, populate
from .support import DiskCase, MemoryCase, counts


class LegacyFixtureTests(DiskCase):
    def test_complete_old_archive_and_constructor_replay(self):
        self.archive.close()
        ids = build_legacy(self.path)
        self.archive = Archive(self.path)
        self.assertEqual(counts(self.archive), (5, 3, 5, 3, 3, 3, 3))
        self.assertEqual(self.archive._store.db.execute(
            "SELECT value FROM metadata WHERE key='version'").fetchone()[0], "1")
        self.assertEqual(self.archive._store.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(list(self.archive._store.db.execute("PRAGMA foreign_key_check")), [])
        historical = self.archive.read_result(ids["job"])
        self.assertEqual(historical["result"]["allocated"]["small"], 3)
        self.assertEqual(historical["result"]["allocated"]["large"], 9)
        self.assertEqual(self.archive.read_result(ids["new_job"])["result"]["allocated"]["whole"], 24)
        self.assertEqual(self.archive.read_result(ids["bow_job"])["result"]["allocated"]["whole"],
                         self.archive.read_field(ids["bow_field"])["values"]["bow"])
        before = counts(self.archive)
        self.archive.close()
        self.assertEqual(build_legacy(self.path), ids)
        self.archive = Archive(self.path)
        self.assertEqual(counts(self.archive), before)
        self.assertEqual(self.archive.head("source"), ids["new_source"])
        self.assertEqual(self.archive.read_result(ids["job"]), historical)


class LegacyMemoryTests(MemoryCase):
    def test_public_end_to_end_fixture(self):
        ids = populate(self.archive)
        before = counts(self.archive)
        self.assertEqual(before, (5, 3, 5, 3, 3, 3, 3))
        self.assertEqual(populate(self.archive), ids)
        self.assertEqual(counts(self.archive), before)
        self.assertEqual(self.archive.head("source"), ids["new_source"])
        result = self.archive.run_job(ids["job"])
        self.assertEqual(result["result"]["allocated"]["small"], 3)
        self.assertEqual(result["result"]["allocated"]["large"], 9)
        self.assertEqual(self.archive.read_result(ids["new_job"])["result"]["allocated"]["whole"], 24)

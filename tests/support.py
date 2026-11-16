import tempfile
import unittest
from pathlib import Path
from gridarchive import Archive
from gridarchive.samples import rectangle, l_source, split_target


def basic(archive):
    source = archive.publish_grid("source", "source-1", l_source())
    target = archive.publish_grid("target", "target-1", split_target())
    field = archive.put_field("field-1", source, {"mass": 12, "missing": None, "zero": 0})
    job = archive.create_job("bound", source, target, field)
    return source, target, field, job


def counts(archive):
    return tuple(archive._store.db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                 for table in ("grids", "heads", "grid_receipts", "fields",
                               "field_receipts", "jobs", "results"))


class MemoryCase(unittest.TestCase):
    def setUp(self):
        self.archive = Archive()

    def tearDown(self):
        self.archive.close()


class DiskCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="gridarchive-test-")
        self.path = str(Path(self.directory.name) / "archive.sqlite")
        self.archive = Archive(self.path)

    def reopen(self, fault=None):
        self.archive.close()
        self.archive = Archive(self.path, fault=fault)
        return self.archive

    def tearDown(self):
        self.archive.close()
        self.directory.cleanup()

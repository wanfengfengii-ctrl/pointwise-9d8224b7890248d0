import sqlite3
from contextlib import contextmanager
from .errors import ValidationError

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO metadata VALUES('version','1');
CREATE TABLE IF NOT EXISTS grids(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS heads(
 name TEXT PRIMARY KEY, revision INTEGER NOT NULL REFERENCES grids(id));
CREATE TABLE IF NOT EXISTS grid_receipts(
 request TEXT PRIMARY KEY, payload TEXT NOT NULL,
 revision INTEGER NOT NULL REFERENCES grids(id));
CREATE TABLE IF NOT EXISTS fields(
 id INTEGER PRIMARY KEY, grid INTEGER NOT NULL REFERENCES grids(id),
 body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS field_receipts(
 request TEXT PRIMARY KEY, payload TEXT NOT NULL,
 version INTEGER NOT NULL REFERENCES fields(id));
CREATE TABLE IF NOT EXISTS jobs(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
 source INTEGER NOT NULL REFERENCES grids(id),
 target INTEGER NOT NULL REFERENCES grids(id),
 field INTEGER NOT NULL REFERENCES fields(id),
 result INTEGER REFERENCES results(id));
CREATE TABLE IF NOT EXISTS results(
 id INTEGER PRIMARY KEY, job INTEGER NOT NULL REFERENCES jobs(id),
 body TEXT NOT NULL);
"""


class Store:
    def __init__(self, path, fault=None):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.fault = fault
        self.db.execute("PRAGMA foreign_keys=ON")
        try:
            self.db.executescript(SCHEMA)
            if self.db.execute("SELECT value FROM metadata WHERE key='version'").fetchone()[0] != "1":
                raise ValidationError("unsupported archive version")
        except BaseException:
            self.db.close()
            raise

    def hit(self, event):
        if self.fault is not None:
            self.fault(event)

    @contextmanager
    def transaction(self, operation):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.hit(operation + ".before_commit")
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def close(self):
        self.db.close()

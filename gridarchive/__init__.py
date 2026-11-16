"""Revision-bound exact area observations and conservative remapping."""
from .errors import Conflict, NotFound, ValidationError
from .storage import Store
from . import grids, fields, jobs, remap


class Archive:
    def __init__(self, path=":memory:", *, fault=None):
        self._store = Store(path, fault)

    def publish_grid(self, name, request, cells):
        return grids.publish_grid(self._store, name, request, cells)

    def head(self, name):
        return grids.head(self._store, name)

    def read_grid(self, revision):
        return grids.read_grid(self._store, revision)

    def grid_receipt(self, request):
        return grids.grid_receipt(self._store, request)

    def put_field(self, request, grid, values):
        return fields.put_field(self._store, request, grid, values)

    def read_field(self, version):
        return fields.read_field(self._store, version)

    def field_receipt(self, request):
        return fields.field_receipt(self._store, request)

    def create_job(self, name, source, target, field):
        return jobs.create_job(self._store, name, source, target, field)

    def run_job(self, job):
        return remap.run_job(self._store, job)

    def read_result(self, job):
        return jobs.read_result(self._store, job)

    def close(self):
        self._store.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

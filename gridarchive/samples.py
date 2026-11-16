"""Finite reproducible SDK1 archive fixture, constructed through public APIs."""
from . import Archive


def rectangle(x, y, right, top):
    return [(x, y), (right, y), (right, top), (x, top), (x, y)]


def l_source():
    return {"mass": [[(0, 0), (1, 0), (1, 1), (3, 1), (3, 2), (0, 2), (0, 0)]],
            "missing": [rectangle(4, 0, 6, 2)],
            "zero": [rectangle(7, 0, 8, 1)]}


def split_target():
    return {"small": [rectangle(0, 0, 1, 1)],
            "large": [rectangle(0, 1, 3, 2)],
            "unknown": [rectangle(4, 0, 5, 2)],
            "zero": [rectangle(7, 0, 8, 1)]}


def populate(archive):
    """Populate the finite SDK1 sample through a caller-owned Archive."""
    source = archive.publish_grid("source", "source-1", l_source())
    target = archive.publish_grid("target", "target-1", split_target())
    field = archive.put_field("field-1", source, {"mass": 12, "missing": None, "zero": 0})
    job = archive.create_job("historical", source, target, field)
    if archive.read_result(job)["result"] is None:
        archive.run_job(job)
    newer = archive.publish_grid("source", "source-2", {
        "lake": [rectangle(0, 0, 4, 4), rectangle(1, 1, 3, 3)]})
    new_target = archive.publish_grid("target", "target-2", {
        "whole": [rectangle(0, 0, 4, 4)]})
    new_field = archive.put_field("field-2", newer, {"lake": 24})
    new_job = archive.create_job("current", newer, new_target, new_field)
    if archive.read_result(new_job)["result"] is None:
        archive.run_job(new_job)
    bow = archive.publish_grid("bow", "bow-1", {
        "bow": [[(0, 0), (2, 2), (0, 2), (2, 0), (0, 0), (-1, 0), (0, 0)]]})
    bow_field = archive.put_field("bow-field", bow, {"bow": "5/2"})
    bow_job = archive.create_job("self-crossing", bow, new_target, bow_field)
    if archive.read_result(bow_job)["result"] is None:
        archive.run_job(bow_job)
    return {"source": source, "target": target, "field": field, "job": job,
            "new_source": newer, "new_target": new_target,
            "new_field": new_field, "new_job": new_job,
            "bow": bow, "bow_field": bow_field, "bow_job": bow_job}


def build_legacy(path):
    """Create a complete old SQLite archive at a caller-owned persistent path.

    Replaying returns the original identities without restoring historical heads
    or republishing results.
    """
    with Archive(path) as archive:
        return populate(archive)

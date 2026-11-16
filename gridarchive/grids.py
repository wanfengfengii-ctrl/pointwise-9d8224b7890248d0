import json
from itertools import combinations
from .codec import dump, identity, name, rational
from .errors import Conflict, NotFound, ValidationError
from .vendor.sdk1 import Region


def _body(cells):
    if not isinstance(cells, dict) or not cells:
        raise ValidationError("grid requires a nonempty cell mapping")
    raw = {}
    regions = {}
    for cell, rings in cells.items():
        name(cell)
        if not isinstance(rings, (list, tuple)):
            raise ValidationError("rings require a sequence")
        copied = []
        for ring in rings:
            if not isinstance(ring, (list, tuple)):
                raise ValidationError("walk requires a sequence")
            walk = []
            for point in ring:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise ValidationError("point requires two coordinates")
                for value in point:
                    rational(value)
                walk.append([str(value) for value in point])
            copied.append(walk)
        raw[cell] = copied
        regions[cell] = Region(copied)
    if sum(region.edge_count for region in regions.values()) > 40:
        raise ValidationError("grid exceeds 40 input edges")
    for cell, region in regions.items():
        if region.area() <= 0:
            raise ValidationError("cell has zero filled area: " + cell)
    for a, b in combinations(sorted(regions), 2):
        if regions[a].intersection_area(regions[b]) > 0:
            raise ValidationError("cell interiors overlap: " + a + ", " + b)
    return dump(raw)


def regions(store, revision):
    identity(revision)
    row = store.db.execute("SELECT body FROM grids WHERE id=?", (revision,)).fetchone()
    if row is None:
        raise NotFound("grid revision")
    return {cell: Region(rings) for cell, rings in json.loads(row["body"]).items()}


def publish_grid(store, grid_name, request, cells):
    name(grid_name)
    name(request)
    body = _body(cells)
    payload = dump({"name": grid_name, "cells": json.loads(body)})
    with store.transaction("grid") as db:
        prior = db.execute("SELECT payload, revision FROM grid_receipts WHERE request=?",
                           (request,)).fetchone()
        if prior is not None:
            if prior["payload"] != payload:
                raise Conflict("grid request already bound")
            return prior["revision"]
        revision = db.execute("INSERT INTO grids(name,body) VALUES(?,?)",
                              (grid_name, body)).lastrowid
        db.execute("INSERT INTO heads VALUES(?,?) ON CONFLICT(name) DO UPDATE SET revision=excluded.revision",
                   (grid_name, revision))
        db.execute("INSERT INTO grid_receipts VALUES(?,?,?)", (request, payload, revision))
    return revision


def head(store, grid_name):
    name(grid_name)
    row = store.db.execute("SELECT revision FROM heads WHERE name=?", (grid_name,)).fetchone()
    if row is None:
        raise NotFound("grid name")
    return row["revision"]


def read_grid(store, revision):
    identity(revision)
    row = store.db.execute("SELECT name,body FROM grids WHERE id=?", (revision,)).fetchone()
    if row is None:
        raise NotFound("grid revision")
    raw = json.loads(row["body"])
    cells = {cell: [[tuple(rational(v) for v in point) for point in ring]
                    for ring in rings] for cell, rings in raw.items()}
    return {"id": revision, "name": row["name"], "cells": cells, "raw": raw}


def grid_receipt(store, request):
    name(request)
    row = store.db.execute("SELECT revision FROM grid_receipts WHERE request=?", (request,)).fetchone()
    if row is None:
        raise NotFound("grid receipt")
    return row["revision"]

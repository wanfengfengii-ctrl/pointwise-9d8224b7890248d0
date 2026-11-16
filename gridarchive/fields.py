import json
from .codec import dump, identity, name, rational
from .errors import Conflict, NotFound, ValidationError
from .grids import read_grid


def put_field(store, request, grid, values):
    name(request)
    identity(grid)
    cells = read_grid(store, grid)["cells"]
    if not isinstance(values, dict) or set(values) != set(cells):
        raise ValidationError("field must cover exactly the cells of its grid revision")
    body = dump({cell: None if value is None else str(rational(value))
                 for cell, value in values.items()})
    payload = dump({"grid": grid, "values": json.loads(body)})
    with store.transaction("field") as db:
        prior = db.execute("SELECT payload,version FROM field_receipts WHERE request=?",
                           (request,)).fetchone()
        if prior is not None:
            if prior["payload"] != payload:
                raise Conflict("field request already bound")
            return prior["version"]
        version = db.execute("INSERT INTO fields(grid,body) VALUES(?,?)",
                             (grid, body)).lastrowid
        db.execute("INSERT INTO field_receipts VALUES(?,?,?)", (request, payload, version))
    return version


def read_field(store, version):
    identity(version)
    row = store.db.execute("SELECT grid,body FROM fields WHERE id=?", (version,)).fetchone()
    if row is None:
        raise NotFound("field version")
    return {"id": version, "grid": row["grid"],
            "values": {cell: None if value is None else rational(value)
                       for cell, value in json.loads(row["body"]).items()}}


def field_receipt(store, request):
    name(request)
    row = store.db.execute("SELECT version FROM field_receipts WHERE request=?", (request,)).fetchone()
    if row is None:
        raise NotFound("field receipt")
    return row["version"]

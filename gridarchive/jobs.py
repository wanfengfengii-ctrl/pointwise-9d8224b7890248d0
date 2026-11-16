import json
from .codec import identity, name, unpack
from .errors import Conflict, NotFound, ValidationError
from .fields import read_field
from .grids import read_grid


def create_job(store, job_name, source, target, field):
    name(job_name)
    read_grid(store, source)
    read_grid(store, target)
    observation = read_field(store, field)
    if observation["grid"] != source:
        raise ValidationError("field belongs to a different grid revision")
    with store.transaction("job") as db:
        prior = db.execute("SELECT * FROM jobs WHERE name=?", (job_name,)).fetchone()
        if prior is not None:
            if (prior["source"], prior["target"], prior["field"]) != (source, target, field):
                raise Conflict("job name already bound")
            return prior["id"]
        result = db.execute("INSERT INTO jobs(name,source,target,field) VALUES(?,?,?,?)",
                            (job_name, source, target, field)).lastrowid
    return result


def read_result(store, job):
    identity(job)
    row = store.db.execute(
        "SELECT j.*, r.body AS result_body FROM jobs j LEFT JOIN results r ON r.id=j.result WHERE j.id=?",
        (job,)).fetchone()
    if row is None:
        raise NotFound("job")
    return {"job": {"id": row["id"], "name": row["name"], "source": row["source"],
                    "target": row["target"], "field": row["field"]},
            "result_id": row["result"],
            "result": None if row["result_body"] is None else unpack(json.loads(row["result_body"]))}

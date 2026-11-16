import json
from fractions import Fraction
from .errors import ValidationError


def rational(value):
    if isinstance(value, bool) or not isinstance(value, (int, str, Fraction)):
        raise ValidationError("coordinates and totals require int, str or Fraction")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValidationError("invalid rational") from exc


def name(value):
    if not isinstance(value, str) or not value:
        raise ValidationError("identity must be a nonempty string")
    return value


def identity(value):
    if type(value) is not int or value < 1:
        raise ValidationError("persisted identity must be a positive integer")
    return value


def dump(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def pack(value):
    if isinstance(value, Fraction):
        return {"$fraction": [value.numerator, value.denominator]}
    if isinstance(value, dict):
        return {k: pack(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [pack(v) for v in value]
    return value


def unpack(value):
    if isinstance(value, dict):
        if set(value) == {"$fraction"}:
            return Fraction(*value["$fraction"])
        return {k: unpack(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unpack(v) for v in value]
    return value

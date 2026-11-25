"""Validation against the public JSON Schemas used by the editable checkout."""

import json
from functools import cache

from jsonschema import Draft202012Validator

from .config import ROOT


@cache
def validator(kind):
    name = kind if kind in ("workload", "run_config") else "records"
    schema = json.loads((ROOT / "schemas" / f"{name}.schema.json").read_bytes())
    if name == "records":
        schema = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{kind}"}
    return Draft202012Validator(schema)


def validate_record(kind, record):
    validator(kind).validate(record)

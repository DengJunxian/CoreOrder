import hashlib
import json
from pathlib import Path

from pams.utils.json_extends import json_extends

ROOT = Path(__file__).resolve().parents[2]


def load_workload(raw):
    settings = json.loads(raw.decode("utf-8"))
    if not isinstance(settings, dict) or not isinstance(settings.get("simulation"), dict):
        raise ValueError("the workload must be a PAMS JSON object with a simulation object")
    # The JSON decoder accepts non-finite values that the run records cannot represent.
    json.dumps(settings, allow_nan=False)
    return settings


def incremental_workload(settings):
    effective = settings.copy()
    for name in settings["simulation"]["markets"]:
        group = json_extends(settings, name, settings[name], excludes_fields=["from", "to"])
        if group.get("class") != "Market":
            raise NotImplementedError(f"incremental restore requires PAMS Market in group {name!r}")
        effective[name] = {**settings[name], "class": "CoreOrderMarket"}
    return effective


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False, ensure_ascii=False) + "\n").encode()


def canonical_workload_hash(settings):
    text = json.dumps(settings, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return sha256(text.encode())


def sha256(data):
    return hashlib.sha256(data).hexdigest()

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_workload(raw):
    settings = json.loads(raw.decode("utf-8"))
    if not isinstance(settings, dict) or not isinstance(settings.get("simulation"), dict):
        raise ValueError("the workload must be a PAMS JSON object with a simulation object")
    # The JSON decoder accepts non-finite values that the run records cannot represent.
    json.dumps(settings, allow_nan=False)
    return settings


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False, ensure_ascii=False) + "\n").encode()


def sha256(data):
    return hashlib.sha256(data).hexdigest()

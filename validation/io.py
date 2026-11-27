"""Immutable JSON evidence files. SPDX-License-Identifier: EPL-1.0."""
import gzip
import json
from pathlib import Path


def read(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with path.open("xb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
                stream.write(json.dumps(value, separators=(",", ":"), allow_nan=False).encode())
    else:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)

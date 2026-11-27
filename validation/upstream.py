"""Load ONLY the verified PAMS source, never the installed or optimized package.

SPDX-License-Identifier: EPL-1.0
"""
import hashlib
import importlib
import json
from pathlib import Path
import sys

from . import PAMS_SHA


def verify_source(root):
    root = Path(root).resolve()
    manifest = json.loads(Path(__file__).with_name("upstream-files.json").read_text())
    if manifest["upstream_sha"] != PAMS_SHA:
        raise ValueError("Wrong upstream manifest")
    for name, expected in manifest["blobs"].items():
        data = (root / name).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if actual != expected:
            raise ValueError(f"Modified upstream: {name}")
    expected_python = {k for k in manifest["blobs"] if k.startswith("pams/") and k.endswith(".py")}
    actual_python = {p.relative_to(root).as_posix() for p in (root / "pams").rglob("*.py")}
    if actual_python != expected_python:
        raise ValueError("Unexpected/missing upstream Python files")
    return root


def load(root):
    root = verify_source(root)
    for name, module in list(sys.modules.items()):
        if name == "pams" or name.startswith("pams."):
            path = getattr(module, "__file__", None)
            if path and not Path(path).resolve().is_relative_to(root):
                raise RuntimeError("Another PAMS is already imported")
    sys.path.insert(0, str(root))
    module = importlib.import_module("pams")
    if not Path(module.__file__).resolve().is_relative_to(root):
        raise RuntimeError("PAMS import escaped verified source")
    return module

import json
import subprocess
from importlib import metadata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UPSTREAMS = json.loads((ROOT / "UPSTREAM.lock.json").read_text(encoding="utf-8"))["dependencies"]


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


@pytest.mark.parametrize("dependency", UPSTREAMS, ids=[item["name"] for item in UPSTREAMS])
def test_locked_upstream(dependency):
    path = dependency["path"]
    checkout = ROOT / path
    gitlink, _ = git("ls-files", "--stage", "--", path).split("\t", maxsplit=1)

    assert gitlink.split() == ["160000", dependency["sha"], "0"]
    assert git("config", "-f", ".gitmodules", "--get", f"submodule.{path}.url") == dependency["repo"]
    assert git("rev-parse", "HEAD", cwd=checkout) == dependency["sha"]
    assert not git("status", "--porcelain", "--untracked-files=all", cwd=checkout)
    assert (ROOT / dependency["license_path"]).read_bytes() == (
        ROOT / dependency["license_copy"]
    ).read_bytes()


def test_installed_packages():
    import coreorder
    import pams
    from pams.runners.sequential import SequentialRunner

    distribution = metadata.distribution("pams")
    assert distribution.version == "0.3.0"
    assert json.loads(distribution.read_text("direct_url.json"))["url"] == (ROOT / "vendor/pams").as_uri()
    assert Path(pams.__file__).resolve() == distribution.locate_file("pams/__init__.py").resolve()
    assert Path(coreorder.__file__).resolve() == ROOT / "src/coreorder/__init__.py"
    assert SequentialRunner.__module__ == "pams.runners.sequential"

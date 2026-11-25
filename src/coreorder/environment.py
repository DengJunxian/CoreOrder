import json
import os
import platform
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pams

from .config import ROOT, sha256


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def environment():
    lock = json.loads((ROOT / "UPSTREAM.lock.json").read_bytes())
    upstream = {}
    for dependency in lock["dependencies"]:
        checkout = ROOT / dependency["path"]
        upstream[dependency["name"]] = {
            "required_sha": dependency["sha"],
            "required_version": dependency["version"],
            "sha": git("rev-parse", "--verify", "HEAD", cwd=checkout),
            "dirty": bool(git("status", "--porcelain", "--untracked-files=normal", cwd=checkout)),
        }

    distribution = metadata.distribution("pams")
    direct_url = json.loads(distribution.read_text("direct_url.json") or "{}")
    machine = {
        "processor": platform.processor() or None,
        "logical_cpus": os.cpu_count(),
        "physical_cpus": None,
        "ram_bytes": None,
    }
    if sys.platform == "darwin":
        model, physical, ram = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string", "hw.physicalcpu", "hw.memsize"], text=True
        ).splitlines()
        machine.update(processor=model, physical_cpus=int(physical), ram_bytes=int(ram))

    compiler = shutil.which("c++")
    libc_name, libc_version = platform.libc_ver()
    return {
        "host_id": sha256(platform.node().encode())[:16],
        "os": platform.platform(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "cpu": machine,
        "libc": {
            "name": libc_name or ("libSystem" if sys.platform == "darwin" else None),
            "version": libc_version or None,
        },
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "packages": {dist.metadata["Name"]: dist.version for dist in metadata.distributions()},
        "pams_module": pams.__file__,
        "pams_version": distribution.version,
        "pams_distribution_matches_import": (
            Path(pams.__file__).resolve() == distribution.locate_file("pams/__init__.py").resolve()
        ),
        "pams_install_source": direct_url.get("url"),
        "dependency_lock_hash": sha256((ROOT / "requirements.lock").read_bytes()),
        "git_version": git("--version"),
        "git_sha": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain", "--ignore-submodules=none")),
        "contract_version": lock["contract_version"],
        "upstream": upstream,
        "compiler": (
            subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]
            if compiler else None
        ),
        "run_native_flags": None,
        "external_threads": {
            name: os.environ.get(name)
            for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
        },
    }

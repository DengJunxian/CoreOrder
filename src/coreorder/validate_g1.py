"""Run the two local G1 correctness checks against one clean source revision."""

import sys

from experiments.capture import execute
from validation.io import write

from .config import ROOT
from .contracts import CONTRACT_VERSION
from .environment import git
from .validate_g2 import run as compare_markets


def run(output):
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        print(error, file=sys.stderr)
        return 1
    scope = "local technical checks for the two G1 subgates"
    commands = {
        "heap": ["tests/heap/audit_p06.py", "--current", "--output", str(output / "heap")],
        "heap-member-e": ["tests/heap/audit_p06_member_e.py", "--current",
                          "--output", str(output / "heap-member-e")],
        "native-contracts": ["-m", "pytest", "-q", "tests/native", "tests/layout"],
    }
    reports = {}
    for name, args in commands.items():
        result = execute([sys.executable, "-B", *args], output / f"{name}-command", 360, cwd=ROOT, scope=scope)
        reports[name] = result["status"]
    selected = [(workload, "upstream", "native-serial", 1, layout, None, None)
                for workload in ("smoke", "native-serial-normal", "p09-full-quota") for layout in ("aos", "soa")]
    reports["native-markets"] = (
        "PASS" if compare_markets(output / "native-markets", selected=selected, suite="g1-native") == 0 else "FAIL"
    )
    approved = all(status == "PASS" for status in reports.values())
    write(output / "status.json", {"suite": "g1", "scope": scope, "git_sha": git("rev-parse", "HEAD"),
                                  "contract_version": CONTRACT_VERSION, "checks": reports,
                                  "status": "PASS" if approved else "FAIL"})
    return 0 if approved else 1

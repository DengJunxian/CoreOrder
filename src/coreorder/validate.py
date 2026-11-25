"""CLI handoff to Member E's separately maintained independent validator."""

import json
import subprocess
import sys

from .config import ROOT, json_bytes
from .contracts import CONTRACT_VERSION
from .environment import git


def run_validation(args):
    output = args.output.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        print(f"cannot create validation output {output}: {error}", file=sys.stderr)
        return 1

    identity = {"suite": args.suite, "contract_version": CONTRACT_VERSION, "git_sha": git("rev-parse", "HEAD")}
    entry = ROOT / "validation/e1.py"
    child = output / "e1"
    command = [
        sys.executable, "-m", "validation.e1", "--suite", args.suite,
        "--config", str(ROOT / "configs/workloads/smoke.json"), "--seed", "42",
        "--output", str(child),
    ]
    (output / "command.json").write_bytes(json_bytes({"argv": command, "cwd": str(ROOT)}))
    with (output / "stdout.log").open("w") as stdout, (output / "stderr.log").open("w") as stderr:
        if not entry.is_file():
            status, code = "BLOCKED", 3
            reason = "E1 independent validator is missing at validation/e1.py"
        else:
            result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, check=False)
            (output / "e1_exit_code.txt").write_text(f"{result.returncode}\n")
            status, code = "FAIL", 1
            reason = f"E1 exited with status {result.returncode}"
            if result.returncode == 0:
                try:
                    receipt = json.loads((child / "status.json").read_bytes())
                    checks = receipt["checks"]
                    if (
                        receipt["status"] != "PASS"
                        or any(receipt[key] != value for key, value in identity.items())
                        or any(checks[name] != "PASS" for name in ("events", "step_state", "final_rng"))
                    ):
                        raise ValueError("the fresh E1 receipt does not confirm all required checks")
                    status, code = "PASS", 0
                    reason = "E1 confirmed events, per-step state and complete final RNG"
                except (OSError, ValueError, KeyError, TypeError) as error:
                    reason = f"invalid E1 receipt: {error}"
        if code:
            print(f"{status}: {reason}", file=stderr)

    (output / "status.json").write_bytes(json_bytes({**identity, "status": status, "reason": reason}))
    print(f"{status}: {reason}", file=sys.stderr if code else sys.stdout)
    return code

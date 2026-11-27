"""Run bounded commands and preserve actual stdout, stderr and exit status.

SPDX-License-Identifier: EPL-1.0
"""
import argparse
from contextlib import suppress
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

from validation.io import write


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def environment():
    return {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "machine": platform.machine(), "processor": platform.processor(),
            "packages": dict(sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())),
            "thread_environment": {k: os.environ.get(k) for k in
                                   ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
            "power_mode": None, "power_reason": "Not collected; development correctness only"}


def execute(command, directory, timeout=30, *, cwd=None, scope="development command; not a formal system timing result"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    timestamp = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    cleanup = None
    try:
        # Process group permits bounded cleanup of spawned PAMS workers on Windows.
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd,
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                                   start_new_session=os.name != "nt")
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            status = "PASS" if process.returncode == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                try:
                    killed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=2)
                    cleanup = {"tree_kill_exit_code":killed.returncode,
                               "stderr":killed.stderr.decode(errors="replace")}
                except (OSError,subprocess.TimeoutExpired) as error:
                    cleanup = {"tree_kill_error":str(error)}
                if process.poll() is None:
                    process.kill()  # direct owned-process handle when taskkill is restricted
            else:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid,signal.SIGKILL)
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired as error:
                stdout,stderr=error.output or b"",error.stderr or b""
                process.stdout.close()
                process.stderr.close()
                cleanup = {"error":"Descendant retained pipes; process tree cleanup unconfirmed"}
            status = "TIMEOUT"
    except OSError as error:
        stdout, stderr = b"", str(error).encode()
        status, process = "FAIL", None
    elapsed = time.perf_counter() - start
    (directory / "stdout.log").write_bytes(stdout)
    (directory / "stderr.log").write_bytes(stderr)
    record = {"command": command, "cwd": str(cwd or Path.cwd()), "timestamp_utc": timestamp,
              "exit_code": process.returncode if process else None, "status": status,
              "elapsed_s_driver": elapsed, "timeout_s": timeout,
              "censoring": "right" if status == "TIMEOUT" else None,
              "timeout_cleanup":cleanup,
              "git_sha": git("-C", str(cwd or Path.cwd()), "rev-parse", "HEAD"),
              "dirty": bool(git("-C", str(cwd or Path.cwd()), "status", "--porcelain")),
              "scope": scope}
    write(directory / "command.json", record)
    write(directory / "environment.json", environment())
    return record


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--timeout", type=float, default=30)
    p.add_argument("command", nargs=argparse.REMAINDER)
    a = p.parse_args()
    command = a.command[1:] if a.command[:1] == ["--"] else a.command
    if not command or a.timeout <= 0:
        p.error("command and positive timeout required")
    record = execute(command, a.output, a.timeout)
    print(json.dumps(record))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

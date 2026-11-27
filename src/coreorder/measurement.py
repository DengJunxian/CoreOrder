"""Launch one production measurement and retain the parent process receipt."""

import json
import re
import shutil
import sys

from experiments.capture import execute

from .config import ROOT, json_bytes


def perf_tool():
    return shutil.which("perf") if sys.platform.startswith("linux") else None


def pmu_receipt(raw, events, launch):
    rows = []
    if raw.is_file():
        for line in raw.read_text().splitlines():
            if not line or line.startswith("#"):
                continue
            fields = [field.strip() for field in line.split(";")]
            if len(fields) >= 5 and fields[2]:
                value, unit, event, running, percent = fields[:5]
                count = None
                if running.isdecimal() and int(running) > 0:
                    if value.isdecimal():
                        count = int(value)
                    elif unit and re.fullmatch(r"\d+[.,]\d+", value):
                        count = float(value.replace(",", "."))
                rows.append({
                    "event": event, "unit": unit, "count": count,
                    "runtime_ns": running, "percent_running": percent, "reported_value": value,
                })
    complete = len(rows) >= len(events) and all(row["count"] is not None for row in rows)
    return {
        "status": "PASS" if launch["status"] == "PASS" and complete else "FAIL",
        "tool": "Linux perf stat", "events_requested": events, "rows": rows,
        "scope": "Python worker lifetime and inherited tasks; raw unscaled counts",
        "raw_artifact": raw.name if raw.is_file() else None,
    }


def launch_measurement(args, argv):
    output = args.output.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        print(f"cannot create run directory {output}: {error.strerror}", file=sys.stderr)
        return 1

    command = [sys.executable, "-m", "coreorder", *argv, "--_measurement-child",
               "--config", str(args.config.resolve()), "--output", str(output)]
    if args.reference_trace is not None:
        command.extend(("--reference-trace", str(args.reference_trace.resolve())))
    perf = perf_tool() if args.mode == "pmu" else None
    raw = output / "perf-stat.csv"
    if perf:
        events = [flag for event in args.pmu_event for flag in ("-e", event)]
        command = [perf, "stat", "--no-big-num", "--no-scale", "-x", ";",
                   "-o", str(raw), *events, "--", *command]
    receipt = execute(command, output / "launch", timeout=args.timeout, cwd=ROOT,
                      scope="standalone measurement; no G3 experiment admission")
    pmu = pmu_receipt(raw, args.pmu_event, receipt) if perf else None
    if pmu is not None:
        (output / "pmu.json").write_bytes(json_bytes(pmu))
    status_path = output / "status.json"
    metrics_path = output / "metrics.json"
    if status_path.exists() and not metrics_path.exists():
        status = json.loads(status_path.read_bytes())
        status.update(status=receipt["status"] if receipt["status"] != "PASS" else "FAIL",
                      reason="worker did not finish writing records; see launch/command.json")
        if receipt["status"] == "TIMEOUT":
            status["censoring"] = "right"
        status_path.write_bytes(json_bytes(status))
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_bytes())
        if perf is None:
            metrics["process_wall_s"] = receipt["elapsed_s_driver"]
            metrics["metric_sources"]["process_wall_s"] = "measured"
            del metrics["unmeasured"]["process_wall_s"]
        if pmu is not None:
            metrics["pmu"] = pmu
            del metrics["unmeasured"]["pmu"]
            if pmu["status"] == "PASS":
                metrics["metric_sources"]["pmu"] = "measured"
        metrics["missing_reasons"] = metrics["unmeasured"]
        pending = output / ".metrics.json.tmp"
        pending.write_bytes(json_bytes(metrics))
        pending.replace(metrics_path)
    if pmu is not None and pmu["status"] != "PASS" and receipt["status"] == "PASS":
        print(f"PMU collection incomplete (see {output / 'pmu.json'})", file=sys.stderr)
        return 1
    if receipt["status"] != "PASS" or not metrics_path.exists():
        failure = ("UNSUPPORTED" if receipt["exit_code"] == 2 else
                   "FAIL" if receipt["status"] == "PASS" else receipt["status"])
        print(f"{failure} (see {output / 'launch' / 'stderr.log'})", file=sys.stderr)
        return 2 if receipt["exit_code"] == 2 else 1
    print(f"PASS (see {status_path})")
    return 0

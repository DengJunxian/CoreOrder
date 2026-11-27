"""Serial target-host P01 pilot. Run from the clean R3 source with the production extension on PYTHONPATH."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import resource
import sys
from time import perf_counter

from experiments.capture import execute
from experiments.protocol import file_hash
from experiments.run import exclusive_host
from validation.io import read, write

PLAN = read("configs/experiments/frozen.json")
SEEDS = (11, 29)
PYTHON = sys.executable
C01 = Path("configs/experiments/workloads/c01/C01b-normal.json")
SECONDS = 30 * 60
ROOT = Path(sys.argv[1]).resolve()
RECEIPTS = ROOT / "chronological.jsonl"
ROWS = [json.loads(line) for line in RECEIPTS.read_text().splitlines()] if RECEIPTS.exists() else []
START = perf_counter()
if ROWS:
    previous = datetime.fromisoformat(read(ROOT / "session.json")["started_utc"])
    START -= (datetime.now(timezone.utc) - previous).total_seconds()
MASK = [0, 2, 4, 6, 8, 10, 12, 14]
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
               "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")


def conditions():
    sysfs = Path("/sys/class")
    return {"affinity": sorted(os.sched_getaffinity(0)),
            "loadavg": Path("/proc/loadavg").read_text().strip(),
            "guest_cpu_stat": Path("/proc/stat").read_text().splitlines()[0],
            "sensors": {str(path): path.read_text().strip() for pattern in (
                "thermal/thermal_zone*/temp", "hwmon/hwmon*/temp*_input", "power_supply/*/online",
                "power_supply/*/status") for path in sysfs.glob(pattern)}}


def attempt(label, argv, timeout, **identity):
    previous = next((row for row in ROWS if row["id"] == label), None)
    if previous:
        assert all(previous[key] == value for key, value in identity.items())
        return previous
    remaining = SECONDS - (perf_counter() - START)
    row = {"id": label, **identity, "conditions_before": conditions()}
    if remaining <= 0 or len(ROWS) >= 48:
        row.update(status="NOT_RUN", reason="P01 cap")
    else:
        core = ROOT / label / "core"
        driver = ROOT / label / "driver"
        if driver.exists() and not (driver / "command.json").exists():
            child = read(core / "launch/command.json")
            status = read(core / "status.json")
            assert child["status"] == status["status"] == "PASS" and not child["timeout_cleanup"]
            row.update(command=argv, status="PASS", exit_code=None, timestamp_utc=child["timestamp_utc"],
                       git_sha=child["git_sha"], recovery="Outer driver interrupted; child completed and signed its own receipt")
        else:
            launch = execute(argv, driver, min(timeout, remaining), scope="R4A x86 development pilot")
            row.update({key: launch[key] for key in ("command", "status", "exit_code", "elapsed_s_driver",
                                                   "timestamp_utc", "git_sha", "censoring", "timeout_cleanup")})
            assert not launch["timeout_cleanup"], f"unconfirmed process cleanup: {label}"
        for name in ("manifest", "metrics", "status", "environment", "comparison", "process_copy", "phases"):
            if (core / f"{name}.json").is_file():
                row[f"core_{name}"] = read(core / f"{name}.json")
        internal_launch = core / "launch/command.json"
        if internal_launch.is_file():
            child = read(internal_launch)
            assert not child["timeout_cleanup"], f"unconfirmed worker tree cleanup: {label}"
            row["child_status"] = child["status"]
            if child["status"] == "TIMEOUT":
                row.update(status="TIMEOUT", censoring="right")
        raw = ROOT / label
        row["raw_bytes"] = sum(path.stat().st_size for path in raw.rglob("*") if path.is_file())
    row["conditions_after"] = conditions()
    ROWS.append(row)
    with (ROOT / "chronological.jsonl").open("a", encoding="utf8") as summary:
        summary.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(label, row["status"], row.get("elapsed_s_driver"), row.get("raw_bytes"), flush=True)
    return row


def workload_path(workload):
    item = PLAN["workloads"][workload]
    path = Path(item["path"])
    assert file_hash(path) == item["input_sha256"]
    return path


def core(workload, seed, backend, heap, layout=None, workers=1, mode="timing", reference=None, timeout=30):
    assert seed in SEEDS and heap in ("upstream", "incremental") and layout in (None, "aos", "soa")
    label = "-".join(map(str, [mode, workload, seed, backend, heap, layout or "na", workers]))
    path = C01 if workload == "C01b-normal" else workload_path(workload)
    config = ["--mode", mode, "--timeout", str(timeout), "--config", str(path), "--seed", str(seed),
              "--output", str(ROOT / label / "core"), "--backend", backend,
              "--workers", str(workers), "--book-restore", heap]
    if layout:
        config += ["--layout", layout]
    if backend == "native-parallel":
        config += ["--grain", "128", "--schedule", "static"]
    if reference:
        config += ["--reference-trace", str(reference)]
    return attempt(label, [PYTHON, "-m", "coreorder", "run", *config], timeout + 10, kind=mode, workload=workload,
                   seed=seed, backend=backend, heap=heap, layout=layout, workers=workers, config_sha256=file_hash(path))


def oracle(workload, seed, timeout):
    label = f"oracle-{workload}-{seed}"
    path = C01 if workload == "C01b-normal" else workload_path(workload)
    output = ROOT / label / "trace.json.gz"
    row = attempt(label, [PYTHON, "-m", "validation", "collect", "--config", str(path), "--seed", str(seed),
                         "--pams-root", "vendor/pams", "--output", str(output)], timeout,
                  kind="oracle", workload=workload, seed=seed, config_sha256=file_hash(path))
    return output if row["status"] == "PASS" else None


def run():
    attempt("smoke", [PYTHON, "-m", "coreorder", "validate", "--suite", "smoke",
                      "--output", str(ROOT / "smoke/core")], 30, kind="correctness")
    reference = oracle("C01b-normal", 11, 30)
    if reference:
        for backend, layout, workers in (("py-process", None, 4), ("native-serial", "aos", 1),
                                          ("native-serial", "soa", 1), ("native-parallel", "aos", 4),
                                          ("native-parallel", "soa", 4)):
            core("C01b-normal", 11, backend, "incremental", layout, workers, "validation", reference)

    for seed in SEEDS:
        for backend, layout, workers in (("py-seq", None, 1), ("native-serial", "aos", 1)):
            core("W0-CI2002", seed, backend, "upstream", layout, workers)
    for backend, layout, workers in (("py-thread", None, 4), ("py-process", None, 4)):
        core("W0-CI2002", 11, backend, "upstream", layout, workers)
    core("W0-H", 11, "py-seq", "incremental")
    for workload in ("W1-H", "W2-H"):
        for heap in ("upstream", "incremental"):
            core(workload, 11, "py-seq", heap)
    for workload, seed in (("W1-SMALL-BATCH", 11), ("W2-MEDIUM-BATCH", 29), ("W3-LARGE-MULTI", 11)):
        for backend, layout, workers in (("py-seq", None, 1), ("native-serial", "aos", 1),
                                          ("native-parallel", "aos", 4), ("native-parallel", "soa", 4)):
            core(workload, seed, backend, "incremental", layout, workers)
    core("W3-LARGE-MULTI", 11, "native-parallel", "incremental", "aos", 8)

    for workload, seed in (("W0-CI2002", 11), ("W1-SMALL-BATCH", 11),
                           ("W2-MEDIUM-BATCH", 29), ("W3-LARGE-MULTI", 11)):
        reference = oracle(workload, seed, 180)
        if reference:
            core(workload, seed, "native-serial", "upstream" if workload == "W0-CI2002" else "incremental",
                 "aos", mode="validation", reference=reference, timeout=180)

    core("W2-H", 11, "native-parallel", "incremental", "aos", 4, "profile", timeout=60)
    output = ROOT / "capture/input"
    captured = attempt("capture", [PYTHON, "docs/roles/A/evidence/pilot_p11.py", "child",
                                   str(workload_path("W2-H")), "11", "native-serial",
                                   "incremental", "capture", str(output)], 60, kind="capture", seed=11)
    if captured["status"] == "PASS":
        meta = read(output / "capture.json")
        capture = output / "input.aos"
        assert file_hash(capture) == meta["sha256"] and capture.stat().st_size == meta["stride"] * meta["rows"]
        for size in (128, 512, 2048, 4096, 8192):
            if size > meta["rows"]:
                continue
            repeats = max(500, 2_000_000 // size)
            results = []
            for layout in ("aos", "soa"):
                label = f"replay-{size}-{layout}"
                destination = ROOT / label / "replay.json"
                attempt(label, [PYTHON, "-m", "experiments.replay", "--input", str(capture),
                                "--sha256", meta["sha256"], "--rows", str(size), "--repeats", str(repeats),
                                "--layout", layout, "--workers", "1", "--grain", "128", "--schedule", "static",
                                "--backend", "native-serial", "--output", str(destination)], 10,
                        kind="replay", rows=size, layout=layout)
                if destination.is_file():
                    results.append(read(destination)["output_sha256"])
            assert len(set(results)) <= 1, f"replay output differs at {size}"


assert PLAN["pilot_seeds"] == list(SEEDS)
assert set(SEEDS).isdisjoint(PLAN["formal_seeds"])
assert sorted(os.sched_getaffinity(0)) == MASK
assert all(os.environ.get(key) == "1" for key in THREAD_VARS)
ROOT.mkdir(mode=0o700, exist_ok=bool(ROWS))
resource.setrlimit(resource.RLIMIT_AS, (7 * 1024**3, resource.getrlimit(resource.RLIMIT_AS)[1]))
with exclusive_host(False, ROOT):
    if not ROWS:
        write(ROOT / "session.json", {"started_utc": datetime.now(timezone.utc).isoformat(),
                                      "control": conditions(), "RLIMIT_AS": resource.getrlimit(resource.RLIMIT_AS),
                                      "external_threads": {key: os.environ[key] for key in THREAD_VARS}})
    run()
assert sum(row.get("kind") == "timing" for row in ROWS) == 24 and len(ROWS) <= 48
write(ROOT / "end.json", {"elapsed_s": perf_counter() - START, "attempts": len(ROWS), "control": conditions()})

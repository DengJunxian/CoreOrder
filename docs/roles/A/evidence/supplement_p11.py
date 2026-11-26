"""Repeat censored counter runs at a diagnostic limit and replay real input rows."""

import json
from pathlib import Path
import sys

from experiments.capture import execute
from validation.io import read, write


def main(root, script):
    primary = root / "runs"
    output = root / "supplement"
    output.mkdir()
    attempts = read(primary / "chronological.json")
    superseded = [row for row in attempts if row["purpose"] == "heap" and row["status"] == "TIMEOUT"]
    for original in superseded:
        case = original["case"] + "-60s"
        path = output / case
        config = primary / "workloads" / f"{original['workload']}.json"
        command = [sys.executable, "-B", script, "child", str(config), str(original["seed"]),
                   original["backend"], original["restore"], "heap", str(path)]
        receipt = execute(command, output / f"{case}-command", 60)
        result = {**original, "case": case, "status": receipt["status"], "timeout_s": 60,
                  "process_elapsed_s": receipt["elapsed_s_driver"], "run": str(path)}
        if receipt["status"] == "PASS":
            result["summary"] = read(path / "summary.json")
            timing = next(row for row in attempts if row["purpose"] == "timing"
                          and row["workload"] == original["workload"] and row["seed"] == original["seed"]
                          and row["backend"] == original["backend"] and row["restore"] == original["restore"])
            for key in ("state_hash", "rng_hash", "orders_admitted"):
                assert timing["summary"][key] == result["summary"][key]
        attempts.append(result)
        print(case, receipt["status"], round(receipt["elapsed_s_driver"], 3), flush=True)
        write(output / f"{case}-ledger.json", attempts)
    write(primary / "chronological-final.json", attempts)

    for workload in ("W0-CI2002", "W1-H"):
        outputs = []
        for profile in (False, True):
            label = f"E-{workload}-{'profile' if profile else 'summary'}"
            target = output / label
            command = [sys.executable, "-B", "-m", "experiments.diagnostic",
                       "--config", str(primary / "workloads" / f"{workload}.json"),
                       "--pams-root", str(Path("vendor/pams").resolve()),
                       "--seed", "11", "--output", str(target)]
            if profile:
                command.append("--profile")
            receipt = execute(command, output / f"{label}-command", 30)
            assert receipt["status"] == "PASS", label
            outputs.append(read(target / "diagnostic.json"))
        for key in ("event_counts", "event_stream_hash", "final_hash", "rng_hash"):
            assert outputs[0][key] == outputs[1][key], key
        ours = read(primary / f"{workload}-11-py-seq-upstream-verify" / "summary.json")
        for e, a in (("OrderLog", "order"), ("ExecutionLog", "execution"),
                     ("ExpirationLog", "expiration"), ("CancelLog", "cancel")):
            assert outputs[0]["event_counts"].get(e, 0) == ours["event_counts"].get(a, 0)
        print(workload, "E stock profile/summary matched ordered events, final state and RNG; A event counts agree.", flush=True)

    source = primary / "W2-H-11-native-serial-incremental-capture"
    capture = read(source / "capture.json")
    _compile = execute([
        "c++", "-std=c++17", "-O3", "-fno-fast-math", "-ffp-contract=off", "-I", "include",
        "native/fcn/evaluate.cpp", str(root / "replay_p11.cpp"), "-o", str(output / "replay"),
    ], output / "replay-build", 30)
    assert _compile["status"] == "PASS"
    values = [
        str(output / "replay"), str(source / "input.aos"), "2048", str(output / "output.aos"),
    ]
    receipt = execute(values, output / "replay-command", 30)
    assert receipt["status"] == "PASS"
    result = json.loads((output / "replay-command/stdout.log").read_text())
    import numpy as np

    from coreorder.config import sha256
    from coreorder.contracts import INPUT_DTYPE
    from coreorder.native_serial import load_native_serial

    payload = (source / "input.aos").read_bytes()
    assert sha256(payload) == capture["sha256"]
    rows = np.frombuffer(payload, dtype=INPUT_DTYPE)
    expected = load_native_serial().Evaluator(parallel=False).aos(rows).tobytes()
    assert result["rows"] == capture["rows"] == len(rows)
    assert expected == (output / "output.aos").read_bytes()
    result.update(input_sha256=capture["sha256"], output_sha256=sha256(expected),
                  replay_row_evaluations=result["rows"] * result["repeats"])
    write(output / "replay.json", result)
    print("Production bare kernel replay matched binding output", result, flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), str(Path(sys.argv[2]).resolve()))

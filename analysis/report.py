"""Summarize sealed CoreOrder evidence with complete, seed-level pairing."""

import argparse
import csv
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median, quantiles

from jsonschema import ValidationError

from experiments.evidence import validation_binding
from experiments.protocol import DEFAULT, Protocol, condition, file_hash, positive, require
from experiments.run import FORMAL, mode_for, qualify_external, read_batch, stage_rows
from validation.io import read, write
from validation.records import eligible

from .pmu import POLICY as PMU_POLICY, qualify_attempt

OUTCOMES = ("PASS", "FAIL", "TIMEOUT", "UNSUPPORTED", "NOT_RUN")


def describe(values):
    if not values:
        return {"n": 0, "median": None, "q1": None, "q3": None, "iqr": None}
    q1, _, q3 = quantiles(values, n=4, method="inclusive") if len(values) > 1 else [values[0]] * 3
    return {"n": len(values), "median": median(values), "q1": q1, "q3": q3, "iqr": q3 - q1}


def seed_interval(effects, stats):
    rng = random.Random(stats["bootstrap_seed"])
    n = len(effects)
    draws = [math.exp(math.fsum(rng.choices(effects, k=n)) / n) for _ in range(stats["bootstrap_resamples"])]
    tails = (1 - stats["confidence_level"]) / 2
    draws.sort()
    return [percentile(draws, tails), percentile(draws, 1 - tails)]


def percentile(sorted_values, fraction):
    index = fraction * (len(sorted_values) - 1)
    low = math.floor(index)
    high = math.ceil(index)
    return sorted_values[low] + (index - low) * (sorted_values[high] - sorted_values[low])


def measured_times(record):
    metrics = record["metrics"]
    return {key: metrics[key] for key in ("setup_s", "simulation_s", "process_wall_s")}


def plot_source(item):
    manifest = item["record"]["manifest"]
    return {"run_id": manifest["run_id"], "raw_directory": str(item["directory"]),
            "record_sha256": item["files_sha256"]["record.json"]}


def verified_run(protocol, row, attempt, attempts, runtime, external):
    record = attempt["record"]
    status, manifest = record["status"], record["manifest"]
    binding = record["validation"]
    if binding is None:
        require(status["status"] != "PASS" or mode_for(row) in ("validation", "replay"),
                "completed measurement has no independent validation binding")
        return
    require(status["validation_status"] == "PASS", "raw validation outcome differs")
    # Timing rows freeze the V01 identity explicitly. Diagnostic rows reuse the
    # exact condition (including effective configuration) in the same V01 batch.
    expected = condition(protocol.workloads[row["workload"]], row, runtime)
    if "v01" in row:
        require(binding["case_id"] == row["v01"], "raw validation case differs from schedule")
    if external is None:
        require(binding["case_id"] in attempts, "bound validation attempt missing")
        receipt, actual = validation_binding(attempts[binding["case_id"]], expected, attempts)
    else:
        require(binding["case_id"] in external, "bound V01 case is unapproved")
        receipt, actual = external[binding["case_id"]]
        require(receipt["identity"] == expected, "timing condition differs from approved V01")
    require({"case_id": binding["case_id"], **actual} == binding and
            status["reference_run_id"] == receipt["reference_run_id"], "bound receipt or oracle differs")
    if status["status"] == "PASS":
        require(receipt["production_final"] == {key: status[key] for key in ("final_state_hash", "rng_hash")},
                "measurement final state or RNG differs from its receipt")
        if mode_for(row) == "timing":
            if external is not None and not row["warmup"]:
                require(eligible(manifest, record["metrics"], status), "ineligible formal timing record")
            require(all(positive(value) for value in measured_times(record).values()) and
                    all(record["metrics"]["metric_sources"].get(key) == "measured"
                        for key in measured_times(record)), "incomplete measured boundaries")


def observations(protocol, rows, attempts, runtime, external, receipts=None):
    output = []
    for row in rows:
        attempt = attempts.get(row["id"])
        planned = {"case_id": row["id"], "phase": row["phase"], "workload": row["workload"],
                   "seed": row["seed"], "repeat": row.get("repeat"), "warmup": row.get("warmup", False),
                   "group": row.get("group"), "variant": row.get("variant"), "block_id": row.get("block_id"),
                   "order_position": row.get("order_position"), "mode": mode_for(row), "host_id": runtime["host_id"],
                   **row["settings"]}
        if attempt is None:
            output.append({**planned, "status": "NOT_RUN", "reason": "no completed attempt", "run_id": None,
                           "backend_effective": None})
            continue
        verified_run(protocol, row, attempt, attempts, runtime, external)
        record = attempt["record"]
        status, metrics = record["status"], record["metrics"]
        if mode_for(row) == "validation" and status["status"] == "PASS" and row.get("reference") not in (None, row["id"]):
            validation_binding(attempt, condition(protocol.workloads[row["workload"]], row, runtime), attempts)
        actual = {**planned, **plot_source(attempt), "status": status["status"], "reason": status["reason"],
                  "censoring": status["censoring"], "backend_effective": record["manifest"]["backend_effective"],
                  "validation_status": status["validation_status"],
                  "validation_run_id": record["manifest"]["validation_run_id"]}
        if status["status"] == "PASS":
            if mode_for(row) == "timing":
                actual["timings_ms"] = {key: value * 1000 for key, value in measured_times(record).items()}
            elif mode_for(row) == "profile":
                actual["phases_ms"] = {key: None if metrics[key] is None else metrics[key] * 1000 for key in
                                       ("draw_pack_s", "native_compute_s", "rebuild_orders_s", "handle_orders_s",
                                        "optional_restore_s")}
            elif mode_for(row) == "replay":
                actual["replay"] = metrics["replay"]
        if mode_for(row) == "pmu":
            if status["status"] == "PASS":
                actual["pmu_quality"] = qualify_attempt(protocol, row, attempt, receipts)
                if actual["pmu_quality"]["status"] == "QUALIFIED":
                    actual["pmu"] = metrics["pmu"]
            elif status["status"] != "NOT_RUN":
                actual["pmu_quality"] = {"status": "INELIGIBLE", "policy": PMU_POLICY,
                                         "reasons": [f'raw_run_{status["status"].lower()}']}
        if status["status"] == "TIMEOUT":
            command = read(attempt["directory"] / record["command"])
            actual["right_censored_driver_s"] = command["timeout_s"]
        output.append(actual)
    return output


def compare_groups(groups, rows, expected_seeds, repeats, stats):
    by_block = defaultdict(dict)
    for row in rows:
        if row["mode"] == "timing" and not row["warmup"]:
            key = (row["host_id"], row["workload"], row["seed"], row["repeat"], row["group"], row["block_id"])
            require(row["variant"] not in by_block[key], "duplicate variant in timing block")
            by_block[key][row["variant"]] = row
    results = []
    for group in groups:
        variants = {variant["id"]: variant for variant in group["variants"]}
        related = {key: block for key, block in by_block.items() if key[4] == group["id"]}
        if not related:
            continue
        require(len({key[0] for key in related}) == 1 and all(key[1] == group["workload"] for key in related),
                "a comparison contains multiple hosts or workloads")
        require(len(related) == len(expected_seeds) * repeats, "planned block count differs from experiment")
        require({key[2:4] for key in related} ==
                {(seed, repeat) for seed in expected_seeds for repeat in range(1, repeats + 1)},
                "wrong seed/repeat pairing")
        for baseline, challenger in group["ordered_pairs"]:
            pairs = []
            effects = defaultdict(list)
            times = {name: [] for name in (baseline, challenger)}
            for key, block in related.items():
                require(key[2] in expected_seeds and key[3] in range(1, repeats + 1), "unexpected seed or repeat")
                item = {"seed": key[2], "repeat": key[3], "block_id": key[5]}
                for role, variant in (("reference", baseline), ("variant", challenger)):
                    row = block.get(variant)
                    observed = {k: row.get(k) for k in ("case_id", "run_id", "status", "censoring",
                                                        "right_censored_driver_s", "reason", "record_sha256",
                                                        "raw_directory")} if row else {"status": "NOT_RUN"}
                    if row and row["status"] == "PASS":
                        observed["timings_ms"] = row["timings_ms"]
                        times[variant].append(row["timings_ms"]["simulation_s"])
                    item[role] = observed
                ref, target = item["reference"], item["variant"]
                if ref["status"] == target["status"] == "PASS":
                    effect = math.log(ref["timings_ms"]["simulation_s"]) - math.log(target["timings_ms"]["simulation_s"])
                    item["log_ratio"] = effect
                    effects[key[2]].append(effect)
                else:
                    item["log_ratio"] = None
                pairs.append(item)
            complete = all(len(effects[key]) == repeats for key in expected_seeds)
            seed_effects = {str(key): {"n_pairs": len(effects[key]),
                                       "median_log_ratio": median(effects[key]) if len(effects[key]) == repeats else None}
                            for key in expected_seeds}
            medians = [row["median_log_ratio"] for row in seed_effects.values()] if complete else []
            speedup = math.exp(math.fsum(medians) / len(medians)) if complete else None
            interval = seed_interval(medians, stats) if complete else None
            count = variants[challenger]["workers"]
            worker_ratio = (count / variants[baseline]["workers"]
                            if variants[baseline]["backend"] == "native-serial" and
                            variants[challenger]["backend"] == "native-parallel" and
                            variants[baseline]["layout"] == variants[challenger]["layout"] and
                            variants[baseline]["book_restore"] == variants[challenger]["book_restore"] else None)
            results.append({"group": group["id"], "phase": group["experiment"], "workload": group["workload"],
                            "reference": baseline, "variant": challenger, "workers": count,
                            "status": "PASS" if complete else "INCOMPLETE",
                            "speedup": speedup, "speedup_ci95": interval,
                            "parallel_efficiency": speedup / worker_ratio if complete and worker_ratio else None,
                            "efficiency_ci95": [value / worker_ratio for value in interval]
                            if complete and worker_ratio else None,
                            "seed_effects": seed_effects, "blocks": pairs,
                            "simulation_ms": {name: describe(values) for name, values in times.items()}})
    return results


def read_source(protocol, source, receipts, development):
    batch = read(source / "batch.json")
    stage = batch["stage"]
    require((stage not in FORMAL) == development, "report scope must match --development and the batch")
    rows = stage_rows(protocol, stage, batch["selected_cases"])
    batch, attempts = read_batch(source, protocol, rows)
    external = qualify_external(protocol, batch["runtime"], receipts) if stage in FORMAL else None
    return batch, observations(protocol, rows, attempts, batch["runtime"], external,
                               receipts if stage in FORMAL else None)


def summary(protocol, batch, rows, extra):
    stats = protocol.plan["statistics"]
    stage = batch["stage"]
    groups, seeds, repeats = protocol.plan["pairing_groups"], protocol.plan["formal_seeds"], protocol.plan["timing_repeats_per_seed"]
    if stage == "pilot":
        groups, seeds, repeats = [protocol.pilot()[1]], protocol.plan["pilot_seeds"], 2
    outcomes = Counter(row["status"] for row in rows)
    missing = Counter()
    for row in rows:
        if row["mode"] == "timing":
            missing.update(key for key in ("setup_s", "simulation_s", "process_wall_s")
                           if key not in row.get("timings_ms", {}))
        if row["mode"] == "profile":
            phases = ("handle_orders_s", "optional_restore_s")
            if row["backend"].startswith("native"):
                phases += ("draw_pack_s", "native_compute_s", "rebuild_orders_s")
            missing.update(key for key in phases if row.get("phases_ms", {}).get(key) is None)
        if row["mode"] in ("pmu", "replay") and row["mode"] not in row:
            missing[row["mode"]] += 1
    pmu_rows = [row for row in rows + extra if row["mode"] == "pmu"]
    pmu_counts = Counter(row.get("pmu_quality", {}).get("status", "NOT_RUN") for row in pmu_rows)
    by_variant = defaultdict(list)
    for row in rows:
        if row.get("timings_ms") and not row["warmup"]:
            for key, value in row["timings_ms"].items():
                by_variant[(row["group"], row["variant"], key)].append(value)
    return {"scope": batch["scope"], "stage": stage, "protocol_hash": protocol.identity, "runtime": batch["runtime"],
            "statistics": {"unit": "seed", "required_seeds": seeds, "required_repeats": repeats,
                           "bootstrap_resamples": stats["bootstrap_resamples"], "bootstrap_seed": stats["bootstrap_seed"],
                           "confidence_level": stats["confidence_level"]},
            "counts": {status: outcomes[status] for status in OUTCOMES},
            "warmups_by_status": dict(Counter(row["status"] for row in rows if row["warmup"])),
            "missing_time_fields": dict(missing),
            "pmu_quality": {"policy": PMU_POLICY, "counts": dict(pmu_counts),
                            "missing_qualified_runs": len(pmu_rows) - pmu_counts["QUALIFIED"]},
            "timing_descriptives_ms": [{"group": group, "variant": variant, "field": key, **describe(values)}
                                       for (group, variant, key), values in sorted(by_variant.items())],
            "comparisons": compare_groups(groups, rows, seeds, repeats, stats), "rows": rows, "additional_sources": extra}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT)
    parser.add_argument("--input", type=Path, required=True, help="raw batch root")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, help="sealed V01 batch (required in formal scope)")
    parser.add_argument("--diagnostics", type=Path, help="optional sealed E05 batch for the same formal lock")
    parser.add_argument("--correctness", type=Path, action="append", default=[], help="optional sealed C01/V01 batch")
    parser.add_argument("--development", action="store_true", help="label a candidate or pilot report as development")
    parser.add_argument("--figures", action="store_true", help="also render qualified data with Matplotlib")
    args = parser.parse_args(argv)
    try:
        protocol = Protocol(args.plan)
        source = args.input.resolve()
        receipts = args.receipts.resolve() if args.receipts else None
        batch, rows = read_source(protocol, source, receipts, args.development)
        extra = []
        if args.diagnostics:
            diagnostic, diagnostic_rows = read_source(protocol, args.diagnostics.resolve(), receipts, False)
            require(batch["stage"] == "timing" and diagnostic["stage"] == "E05" and
                    batch["runtime"] == diagnostic["runtime"], "wrong diagnostic companion")
            extra.extend(diagnostic_rows)
        for directory in [*args.correctness, *([receipts] if receipts else [])]:
            header = read(directory / "batch.json")
            require(header["stage"] in ("C01", "V01") and header["runtime"] == batch["runtime"],
                    "wrong correctness source identity")
            expected_rows = stage_rows(protocol, header["stage"], header["selected_cases"])
            if header["protocol_hash"] == protocol.identity:
                _, attempt_rows = read_source(protocol, directory.resolve(), None, True)
                extra.extend(attempt_rows)
            elif receipts and directory == receipts and batch["stage"] in FORMAL:
                # Approved V01 was executed before activating G3 on the same source and host.
                from experiments.evidence import read_attempts
                attempts = read_attempts(directory)
                extra.extend(observations(protocol, expected_rows, attempts, batch["runtime"], None))
            else:
                raise ValueError("correctness protocol differs")
        report = summary(protocol, batch, rows, extra)
        all_rows = rows + extra
        run_ids = [row["run_id"] for row in all_rows if row["run_id"] is not None]
        require(len(run_ids) == len(set(run_ids)), "duplicate evidence run ID in report")
        render = None
        if args.figures:
            from .figures import render_figures
            render = render_figures
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=False)
        write(output / "report.json", report)
        with (output / "runs.csv").open("x", newline="", encoding="utf-8") as stream:
            fields = ("case_id", "run_id", "phase", "workload", "seed", "repeat", "warmup", "group", "variant",
                      "block_id", "host_id", "mode", "status", "reason", "censoring", "right_censored_driver_s",
                      "validation_status", "validation_run_id", "setup_ms", "simulation_ms", "process_wall_ms",
                      "record_sha256", "raw_directory", "pmu_quality_status", "pmu_quality_reasons")
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in all_rows:
                times = {key.replace("_s", "_ms"): value for key, value in row.get("timings_ms", {}).items()}
                quality = row.get("pmu_quality", {})
                pmu_status = quality.get("status", "NOT_RUN") if row["mode"] == "pmu" else None
                writer.writerow({**row, **times, "pmu_quality_status": pmu_status,
                                 "pmu_quality_reasons": " | ".join(quality.get("reasons", []))})
        if render:
            render(report, protocol.figures, output)
        print(report["scope"], report["counts"], file_hash(output / "report.json"))
        return 0
    except (ValueError, KeyError, OSError, TypeError, ValidationError, ImportError) as error:
        print(f"report refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

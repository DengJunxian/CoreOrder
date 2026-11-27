"""Generate the leader-approved R4B candidate. Formal execution remains blocked."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from random import Random
import shutil

from experiments.protocol import Protocol, SETTINGS, file_hash, order_seed
from validation.io import read, write

EVENTS = {"cpu-work": ["cycles:u", "instructions:u"],
          "L1-data": ["L1-dcache-loads:u", "L1-dcache-load-misses:u"],
          "branch": ["branches:u", "branch-misses:u"]}
SIZES = [2048, 4096, 8192]


def write_rows(path, rows):
    with path.open("x", encoding="utf8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def draft(original, output, runtime, native, compile_commands, reuse_w2):
    baseline = Protocol(original)
    assert not baseline.active
    plan, lock = baseline.plan, baseline.lock
    assert plan["candidate_id"] == "r4-p12-provisional-v1"
    assert runtime["dirty"] is False and runtime["architecture"] == "x86_64"
    assert native["sha256"] == runtime["native_sha256"]
    required = {"-O3", "-fno-fast-math", "-ffp-contract=off"}
    production = [cmd for cmd in read(compile_commands) if "_coreorder_fcn.dir/native/" in cmd["command"]]
    assert len(production) == 3 and all(required <= set(cmd["command"].split()) for cmd in production)

    output.mkdir()
    shutil.copytree(original / "workloads", output / "workloads")
    for name in ("runlist-C01.jsonl", "figures.json", "plan.template.json"):
        shutil.copy2(original / name, output / name)
    for group in plan["pairing_groups"]:
        if reuse_w2 and group["experiment"] == "E03" and group["workload"] == "W2-MEDIUM-BATCH":
            group.update(workload="W2-H", id="E03-W2-H")
        if group["experiment"] != "E02":
            continue
        if group["workload"] == "W1-SMALL-BATCH":
            group.update(workload="W1-H", id="E02-W1-H")
        group["variants"] = [item for item in group["variants"] if item["workers"] != 8]
        group["ordered_pairs"] = [pair for pair in group["ordered_pairs"] if "native-8" not in pair]

    ledgers, cells, refs = [], {}, {}
    defaults = {"status": "NOT_RUN", "runnable": False, "run_id": None}
    seeds = plan["formal_seeds"]
    for group in plan["pairing_groups"]:
        gid, workload = group["id"], group["workload"]
        config = plan["workloads"][workload]
        raw_hash = config["input_sha256"]
        variants = {item["id"]: {key: item[key] for key in SETTINGS} for item in group["variants"]}
        for variant, settings in variants.items():
            for seed in seeds:
                key = {"input": raw_hash, "effective": config["effective_sha256"][settings["book_restore"]],
                       "numeric_mode": "libm", "seed": seed, **settings}
                short = sha256(json.dumps(key, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
                case = f"V01-{short}"
                oracle = refs.setdefault((raw_hash, seed), {
                    **defaults, "id": f"V01-reference-{raw_hash[:16]}-{seed}", "phase": "V01", "timeout_s": 180,
                    "seed": seed, "workload": workload, "runner": "verified vendor oracle",
                    "settings": {"backend": "py-seq", "book_restore": "upstream", "workers": 1,
                                 "layout": "not_applicable", "grain": None, "schedule": None},
                })
                cells.setdefault(case, {
                    **defaults, "id": case, "phase": "V01", "timeout_s": 180, "seed": seed, "workload": workload,
                    "settings": settings, "reference": oracle["id"], "validation_run_id": None, "aliases": [],
                })["aliases"].append([gid, variant])
                for repeat, warmup_seed in enumerate(plan["warmup_seeds"], 1):
                    if seed == warmup_seed:
                        ledgers.append({**defaults, "id": f"{gid}-{variant}-warmup-{repeat}",
                                        "phase": group["experiment"], "workload": workload, "group": gid,
                                        "variant": variant, "seed": seed, "repeat": repeat, "warmup": True,
                                        "order_seed": None, "block_id": None, "order_position": None,
                                        "settings": settings, "v01": case, "timeout_s": plan["timeout_s"]})
        lookup = {(alias[1], item["seed"]): case for case, item in cells.items() for alias in item["aliases"]
                  if alias[0] == gid}
        for seed in seeds:
            for repeat in range(1, 4):
                block = f"{gid}-{seed}-{repeat}"
                rng = order_seed(plan["order_master_seed"], block)
                order = list(variants)
                Random(rng).shuffle(order)
                for pos, variant in enumerate(order, 1):
                    ledgers.append({**defaults, "id": f"{block}-{variant}", "phase": group["experiment"],
                                    "workload": workload, "group": gid, "variant": variant, "seed": seed,
                                    "repeat": repeat, "warmup": False, "order_seed": rng, "block_id": block,
                                    "order_position": pos, "settings": variants[variant],
                                    "v01": lookup[variant, seed], "timeout_s": plan["timeout_s"]})
    e05 = [row for row in baseline.rows["E05"] if row["phase"] != "E05-replay" or row["rows"] in SIZES]
    for row in e05:
        if reuse_w2 and row["workload"] == "W2-MEDIUM-BATCH":
            row["workload"] = "W2-H"
        if row["phase"] != "E05-PMU":
            continue
        if row["event_group"] == "LLC-branch":
            row.update(event_group="branch", id=row["id"].replace("LLC-branch", "branch"))
        row.update(events=EVENTS[row["event_group"]], reason="R4A target hardware qualification")
    diag = plan["diagnostics"]
    diag.update(PMU_enabled=True, actual_events=EVENTS,
                PMU_event_groups={"cpu-work": "cycles and retired instructions",
                                  "L1-data": "AMD data accesses and L2 requests from L1D misses",
                                  "branch": "retired branches and mispredictions; LLC unavailable in target WSL2"})
    diag["replay"].update(rows=SIZES, kernel_repeats_reason="target calibration required before G3")
    if reuse_w2:
        diag["replay"]["source"]["workload"] = "W2-H"
    plan.update(candidate_id="r4b-leader-approved-candidate", candidate_production_sha=runtime["git_sha"],
                reason="Await complete x86 C01/V01 evidence, E05 replay identity and team signoffs",
                core_condition_count=sum(len(group["variants"]) for group in plan["pairing_groups"]),
                V01_unique_candidate_conditions=len(cells) // 5, V01_candidate_receipts_required=len(cells),
                V01_oracles_required=len(refs), timing_attempts=len(ledgers), E05_rows=len(e05),
                hash_receipt="configs/experiments/R4B-SHA256SUMS")
    plan["notes"].update(core_grain="128, static", host_assumption="WSL guest one vCPU per exposed core, p*=4",
                         steps=("E02 W1-H 20+100, E03/E05 W2-H 8+24, original W3 2+8." if reuse_w2 else
                                "E02 W1-H 20+100. W2 and W3 use original full candidate steps."))
    plan["execution"]["qualification_scope"] = "Validated no-fee markets; reject unsupported automatic execution"
    assert (len(ledgers), sum(row["warmup"] for row in ledgers), len(refs), len(cells), len(e05)) == (493, 58, 20 if reuse_w2 else 25, 125, 76)
    assert all(any(baseline.same_input(row, cell) and row["seed"] == cell["seed"] and row["settings"] == cell["settings"]
                   for cell in cells.values()) for row in e05 if row["phase"] != "E05-replay")
    write_rows(output / "runlist-timing.jsonl", ledgers)
    write_rows(output / "runlist-V01.jsonl", [*refs.values(), *cells.values()])
    write_rows(output / "runlist-E05.jsonl", e05)
    write(output / "frozen.json", plan)
    files = {p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob("*")) if p.is_file()}
    lock.update(candidate_files_sha256=files, candidate_production_sha=runtime["git_sha"],
                clean_audit_checkout=runtime["git_sha"], baseline_schema_sha256=runtime["schemas_sha256"],
                primary_x86={"host_id": runtime["host_id"], "code_sha": runtime["git_sha"],
                             "environment_sha256": runtime["environment_sha256"], "native_module": native,
                             "compiler": runtime["compiler"], "actual_compile_flags": sorted(required),
                             "build_compile_commands_sha256": file_hash(compile_commands),
                             "frequency": {"guest_report_MHz": 1996.203, "effective_physical_frequency": None},
                             "affinity": {"guest_cpus": [0, 2, 4, 6, 8, 10, 12, 14],
                                          "physical_host_mapping": None},
                             "actual_pmu_events": EVENTS})
    write(output / "protocol_lock.json", lock)
    check = Protocol(output)
    assert not check.active and check.rows["C01"] == baseline.rows["C01"]
    print(check.identity, {key: len(rows) for key, rows in check.rows.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("original", "output", "runtime", "native", "compile"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--reuse-w2-h", action="store_true", help="use the further leader-approved W2-H reuse")
    args = parser.parse_args()
    draft(args.original, args.output, read(args.runtime), read(args.native)["native_module"], args.compile, args.reuse_w2_h)

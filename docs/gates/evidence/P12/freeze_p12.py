"""Materialize the blocked R4 protocol candidate and its non-executable ledger."""

import hashlib
import json
from pathlib import Path
import random
import sys

from coreorder.config import incremental_workload
from coreorder.schema import validate_record
from validation.cases import cases as e_cases

ROOT = Path.cwd()
BASE = Path("configs/experiments")
SEEDS = [101, 202, 303, 404, 505]
TIMEOUT = 30
ORDER_MASTER = 20261126


def sha(data):
    return hashlib.sha256(data).hexdigest()


def put(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    return data


def build(output, pilot, evidence):
    output.mkdir()
    checked = json.loads((evidence / "environment.json").read_bytes())
    lineage = json.loads((evidence / "chain/lineage.json").read_bytes())
    template = json.loads((BASE / "plan.template.json").read_bytes())
    assert template["formal_seeds"] == SEEDS and checked["dirty"] is False
    assert all(not row["formal_eligible"] for row in lineage["runs"])
    confirm_native = next(row["native_module"] for row in lineage["runs"] if row["native_module"] is not None)
    assert all(row["git_sha"] == checked["git_sha"] for row in lineage["runs"])
    compile_commands = Path("build/compile_commands.json").read_bytes()
    strict_flags = ("-O3", "-fno-fast-math", "-ffp-contract=off")
    for item in json.loads(compile_commands):
        if Path(item["file"]).relative_to(ROOT).is_relative_to("native"):
            assert set(strict_flags) <= set(item["command"].split())
    workloads = {}

    def add(workload, data, final_path, origin):
        settings = json.loads(data)
        validate_record("workload", settings)
        simulation = settings["simulation"]
        incremental = (json.dumps(incremental_workload(settings), ensure_ascii=False, allow_nan=False) + "\n").encode()
        workloads[workload] = {
            "path": str(final_path), "source": origin,
            "input_sha256": sha(data),
            "effective_sha256": {"upstream": sha(data), "incremental": sha(incremental)},
            "N": sum(settings[group].get("numAgents", 1) for group in simulation["agents"]),
            "M_by_session": [session.get("maxNormalOrders", 1) for session in simulation["sessions"]],
            "K": len(simulation["markets"]),
            "steps_by_session": [session["iterationSteps"] for session in simulation["sessions"]],
        }

    official = Path("vendor/pams/samples/CI2002/config.json")
    source = official.read_bytes()
    assert source == (pilot / "W0-CI2002.json").read_bytes()
    add("W0-CI2002", source, official, "pinned unmodified PAMS CI2002")
    add("W0-H", source, official, "identical W0 bytes, separate H01 pairing group")

    for identifier, name, trading_steps in (
        ("W1-H", "W1-H", None),
        ("W2-H", "W2-H", None),
        ("W1-SMALL-BATCH", "W1-H", 500),
        ("W2-MEDIUM-BATCH", "W2-H", 120),
        ("W3-LARGE-MULTI", "W3-START", None),
    ):
        pilot_bytes = (pilot / f"{name}.json").read_bytes()
        relative = Path("workloads") / f"{identifier}.json"
        if trading_steps is None:
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(pilot_bytes)
            data = pilot_bytes
        else:
            settings = json.loads(pilot_bytes)
            settings["simulation"]["sessions"][-1]["iterationSteps"] = trading_steps
            data = put(output / relative, settings)
        add(identifier, data, BASE / relative, {
            "pilot_reference": name, "pilot_input_sha256": sha(pilot_bytes),
            "provisional_trade_steps": trading_steps,
        })

    fixture_names = []
    for name, settings in e_cases(Path("vendor/pams")).items():
        relative = Path("workloads/c01") / f"{name}.json"
        data = put(output / relative, settings)
        add(name, data, BASE / relative, "unchanged E validation.cases")
        fixture_names.append(name)
    assert len(fixture_names) == 12

    def mode(backend, restore, workers=1, layout="not_applicable"):
        value = {"backend": backend, "book_restore": restore, "workers": workers,
                 "layout": layout, "grain": 128 if backend == "native-parallel" else None,
                 "schedule": "static" if backend == "native-parallel" else None}
        validate_record("run_config", {**value, "seed": SEEDS[0]})
        return value

    def independent_key(workload, settings, seed):
        # Main-host, code, environment and extension are separately mandatory
        # parts of the final V01 identity when an actual receipt is linked.
        data = {"input": workloads[workload]["input_sha256"],
                "effective": workloads[workload]["effective_sha256"][settings["book_restore"]],
                "numeric_mode": "libm", "seed": seed, **settings}
        return sha(json.dumps(data, sort_keys=True, separators=(",", ":")).encode())[:24]

    groups = []
    seq = lambda heap: mode("py-seq", heap)
    native = lambda heap, layout="aos": mode("native-serial", heap, layout=layout)
    parallel = lambda heap, workers, layout="aos": mode("native-parallel", heap, workers, layout)

    def group(experiment, workload, variants, comparisons):
        identity = f"{experiment}-{workload}"
        groups.append({"id": identity, "experiment": experiment, "workload": workload,
                       "variants": [{"id": name, **value} for name, value in variants],
                       "ordered_pairs": comparisons})

    e01 = [("seq", seq("upstream")), ("thread-4", mode("py-thread", "upstream", 4)),
           ("process-4", mode("py-process", "upstream", 4)), ("native-direct", native("upstream")),
           ("native-4", parallel("upstream", 4))]
    group("E01", "W0-CI2002", e01, [["seq", name] for name, _ in e01[1:]])
    for workload in ("W0-H", "W1-H", "W2-H"):
        group("H01", workload, [(heap, seq(heap)) for heap in ("upstream", "incremental")],
              [["upstream", "incremental"]])
    for workload in ("W1-SMALL-BATCH", "W3-LARGE-MULTI"):
        group("E02", workload, [
            ("seq", seq("incremental")), ("native-direct", native("incremental")),
            *((f"native-{workers}", parallel("incremental", workers)) for workers in (1, 2, 4, 8)),
        ], [["seq", "native-direct"], *[["native-direct", f"native-{w}"] for w in (1, 2, 4, 8)]])
    for workload in ("W2-MEDIUM-BATCH", "W3-LARGE-MULTI"):
        group("E03", workload, [
            (f"direct-{layout}", native("incremental", layout)) for layout in ("aos", "soa")
        ] + [(f"parallel-4-{layout}", parallel("incremental", 4, layout)) for layout in ("aos", "soa")],
            [["direct-aos", "direct-soa"], ["parallel-4-aos", "parallel-4-soa"]])

    ledger = []
    validation_cells = {}
    references = {}
    for item in groups:
        workload = item["workload"]
        group_id = item["id"]
        for variant in item["variants"]:
            settings = {k: v for k, v in variant.items() if k != "id"}
            for seed in SEEDS:
                key = independent_key(workload, settings, seed)
                validation_cells.setdefault(key, {
                    "id": f"V01-{key}", "workload": workload, "settings": settings,
                    "seed": seed, "aliases": [], "validation_run_id": None,
                })["aliases"].append([group_id, variant["id"]])
                source_hash = workloads[workload]["input_sha256"]
                references.setdefault((source_hash, seed), {
                    "id": f"V01-reference-{source_hash[:16]}-{seed}",
                    "workload": workload, "seed": seed,
                    "settings": seq("upstream"), "runner": "verified vendor oracle",
                })
            for index, seed in enumerate(SEEDS[:2], 1):
                ledger.append({"id": f"{group_id}-{variant['id']}-warmup-{index}",
                               "phase": item["experiment"], "workload": workload, "seed": seed,
                               "group": group_id, "variant": variant["id"], "warmup": True, "settings": settings, "repeat": index,
                               "block_id": None, "order_seed": None, "order_position": None,
                               "v01": f"V01-{independent_key(workload, settings, seed)}"})
        for seed in SEEDS:
            for repeat in (1, 2, 3):
                block = f"{group_id}-{seed}-{repeat}"
                order_seed = int(sha(f"{ORDER_MASTER}/{block}".encode())[:13], 16)
                variants = item["variants"].copy()
                random.Random(order_seed).shuffle(variants)
                for position, variant in enumerate(variants, 1):
                    settings = {k: v for k, v in variant.items() if k != "id"}
                    ledger.append({"id": f"{block}-{variant['id']}", "phase": item["experiment"],
                                   "workload": workload, "group": group_id, "variant": variant["id"],
                                   "warmup": False, "seed": seed, "repeat": repeat, "block_id": block,
                                   "order_seed": order_seed, "order_position": position, "settings": settings,
                                   "v01": f"V01-{independent_key(workload, settings, seed)}"})

    c01 = []
    c01_modes = []
    for row in template["correctness_settings"]:
        c01_modes.append(mode(row["backend"], row["book_restore"], row.get("workers", 1),
                             row.get("layout", "not_applicable")))
    for workload in fixture_names:
        for seed in SEEDS:
            for index, settings in enumerate(c01_modes):
                c01.append({"id": f"C01-{workload}-{seed}-{index}", "phase": "C01",
                            "workload": workload, "seed": seed, "settings": settings,
                            "reference": f"C01-{workload}-{seed}-0",
                            "runner": "verified vendor oracle" if index == 0 else "candidate"})

    v01 = [{"phase": "V01", **row} for row in references.values()]
    for row in validation_cells.values():
        key = workloads[row["workload"]]["input_sha256"], row["seed"]
        v01.append({"phase": "V01", **row, "reference": references[key]["id"]})
    assert len(ledger) == 527 and len(v01) == 170 and len(c01) == 420

    w2 = "W2-MEDIUM-BATCH"
    replay = {
        "source": {"workload": w2, "seed": 101, "mode": native("incremental"),
                   "receipt": None, "input_sha256": None},
        "rows": [128, 512, 2048, 4096, 8192], "layouts": ["aos", "soa"],
        "samples_per_variant": 3, "warmups_per_variant": 1,
        "source_rule": "capture distinct real rows in original order, take prefixes, never manufacture rows",
        "kernel_repeat_count": None, "kernel_repeats_reason": "calibrate on qualified target before activation",
    }
    mechanisms = {
        "PMU": [(w, s) for w, s in [
            ("W1-H", seq("upstream")), ("W1-H", seq("incremental")),
            (w2, parallel("incremental", 4)), (w2, parallel("incremental", 4, "soa")),
        ]],
        "profile": [("W0-CI2002", seq("upstream")), ("W1-H", seq("upstream")),
                    ("W1-H", seq("incremental")), (w2, native("incremental"))],
    }
    diagnostics = []
    for i, (workload, settings) in enumerate(mechanisms["profile"], 1):
        diagnostics.append({"id": f"E05-profile-{i}", "phase": "E05-profile", "timeout_s": 60,
                            "workload": workload, "settings": settings, "seed": 101})
    for i, (workload, settings) in enumerate(mechanisms["PMU"], 1):
        for event_group in ("cpu-work", "L1-data", "LLC-branch"):
            for repeat in (1, 2):
                diagnostics.append({"id": f"E05-PMU-{i}-{event_group}-{repeat}", "phase": "E05-PMU",
                                    "seed": 101, "workload": workload, "settings": settings,
                                    "event_group": event_group, "events": None, "timeout_s": 30,
                                    "repeat": repeat, "reason": "qualify actual target events and permissions"})
    for size in replay["rows"]:
        for layout in replay["layouts"]:
            for name, settings in (("direct", native("incremental", layout)),
                                   ("pool-4", parallel("incremental", 4, layout))):
                for repeat in range(4):
                    diagnostics.append({"id": f"E05-replay-{size}-{layout}-{name}-{repeat}",
                                        "phase": "E05-replay", "seed": 101, "workload": w2, "settings": settings,
                                        "rows": size, "repeat": repeat, "warmup": repeat == 0, "timeout_s": 30})
    assert len(diagnostics) == 108

    stage_budget = {row["id"]: row["budget_minutes"] for row in template["stages"]}
    formal_minutes = sum(stage_budget.values())
    assert formal_minutes == 460 and formal_minutes + template["reserve_minutes"] == 480
    plan = {**template, "status": "BLOCKED", "runnable": False, "authorized_formal_runs": [],
            "reason": "G2, target qualification, V01, and E4 producer/consumer review are open",
            "candidate_id": "r4-p12-provisional-v1",
            "candidate_production_sha": "92f8bbf08da514dcb24e27b6a815d3947c352798",
            "formal_code_sha": None, "protocol_lock_hash": None,
            "protocol_lock_path": str(BASE / "protocol_lock.json"),
            "hash_receipt": str(BASE / "P12-SHA256SUMS"),
            "workloads": workloads, "pairing_groups": groups, "order_master_seed": ORDER_MASTER,
            "warmup_seeds": SEEDS[:2], "core_condition_count": 31, "timing_attempts": 527,
            "C01_count": 420, "V01_unique_candidate_conditions": len(validation_cells) // 5,
            "V01_candidate_receipts_required": len(validation_cells), "V01_candidate_receipts_accepted": 0,
            "V01_oracles_required": len(references), "E05_rows": len(diagnostics),
            "notes": {
                "host_assumption": "planning bound P=8 p*=4, not yet authorized",
                "core_grain": "128 static, pending target joint qualification",
                "steps": "W1 20+500 and W2 8+120 are candidate calibration points; final target pilot is pending",
                "formal_bench": "keep all required V01; remove E04/W4 and excess thread points before shrinking core workloads",
            },
            "mac_plan": {"limit_minutes": 60, "environment_and_chain": 8, "semantic_validation": 32,
                         "representative_checks": 15, "reserve": 5, "cross_host_ratios": False,
                         "workloads": ["W0-CI2002", "W2-H"],
                         "W0": [seq("upstream"), seq("incremental")],
                         "W2_small": [seq("upstream"), seq("incremental"), native("incremental"),
                                      parallel("incremental", 4), parallel("incremental", 4, "soa")],
                         "requires_separate_C01_and_V01_receipts": True},
            "primary": {"stage_budgets_minutes": stage_budget, "planned_minutes": formal_minutes,
                        "rerun_reserve_minutes": 20, "max_minutes": 480},
            "execution": {
                "V01_attempt_timeout_s": 180, "C01_attempt_timeout_s": 30,
                "timing_attempt_timeout_s": TIMEOUT,
                "phase_clock": "use monotonic elapsed including setup, output, cleanup and cooling; cap each attempt by remaining phase and host budget",
                "py_process": "upstream spawn; retain all outcomes; stop case after timeout",
                "interference": "no concurrent timing; pause on independent thermal/power/background evidence",
                "reruns": "preserve result and reason; correctness requires new SHA and validation before timing; no arbitrary slow-run replacement",
                "timing": "identify direct compute + all business work under matched low-overhead mode; final digest outside simulation time",
            },
            "diagnostics": {"max_minutes": 35, "PMU": 12, "profile": 4, "replay": 10, "setup": 9,
                            "PMU_enabled": False, "actual_events": None,
                            "PMU_event_groups": {
                                "cpu-work": "cycles, instructions and related process CPU-work events",
                                "L1-data": "qualified vendor definitions for L1 data accesses and misses",
                                "LLC-branch": "qualified vendor definitions for LLC and branch events",
                            },
                            "PMU_scope": "whole process unless a separate verified enable/disable measurement scope is recorded",
                            "invalid_events": "null plus reason; preserve enabled and running time",
                            "replay": replay},
            "statistics": {**template["statistics"], "confidence_level": 0.95,
                           "practical_threshold_fraction": 0.05,
                           "show": "raw paired times, median/IQR, and five seed effects",
                           "complete_pairing_requirement": "3 matching blocks for each of 5 seeds",
                           "missing_policy": "no point estimate for incomplete required comparison"},
    }
    put(output / "frozen.json", plan)
    for kind, rows in (("timing", ledger), ("C01", c01), ("V01", v01), ("E05", diagnostics)):
        with (output / f"runlist-{kind}.jsonl").open("x", encoding="utf-8") as stream:
            for row in rows:
                assert row["workload"] in workloads
                assert row["seed"] in SEEDS
                timeout = plan["execution"].get(f"{kind}_attempt_timeout_s", TIMEOUT)
                stream.write(json.dumps({"timeout_s": timeout, **row, "status": "NOT_RUN", "runnable": False,
                                         "run_id": None}, ensure_ascii=False) + "\n")

    figures = [
        {"id": "F1", "source": ["C01", "V01"], "scope": "full correctness with failed rows retained"},
        {"id": "F2", "source": ["H01", "E05"], "scope": "restore operations and inclusive phase contributions"},
        {"id": "F3", "source": ["E01", "E02", "E05"], "scope": "raw times and phase boundaries"},
        {"id": "F4", "source": ["E02"], "scope": "workers curve with complete seed-block effects"},
        {"id": "F5", "source": ["E03", "E05"], "scope": "same-row AoS/SoA, PMU only if qualified"},
        {"id": "F6", "source": ["E02", "E05"], "scope": "bare kernel and system results at their own scopes"},
        {"id": "T7", "source": ["Mac"], "scope": "separate-platform correctness and compatibility"},
        {"id": "P12-smoke", "source": ["local diagnostic run IDs"], "scope": "workload counters, no speed or eligibility"},
    ]
    put(output / "figures.json", {"formal_figures": "NOT_RUN", "figures": figures})
    files = {str(path.relative_to(output)): sha(path.read_bytes())
             for path in sorted(output.rglob("*")) if path.is_file()}

    lock = {
        "state": "BLOCKED", "locked_for_execution": False, "candidate_files_sha256": files,
        "candidate_production_sha": plan["candidate_production_sha"], "clean_audit_checkout": checked["git_sha"],
        "contract_version": checked["contract_version"], "upstream": checked["upstream"],
        "dependency_lock_hash": checked["dependency_lock_hash"],
        "baseline_schema_sha256": {str(path): sha(path.read_bytes()) for path in sorted(Path("schemas").glob("*.json"))},
        "local_Mac": {
            "scope": "only the independently recorded diagnostic chain", "build_compile_commands_sha256":
                sha(compile_commands), "observed_strict_flags": strict_flags,
            "environment_file_sha256": sha((evidence / "environment.json").read_bytes()),
            "native_module": confirm_native, "os": checked["os"], "architecture": checked["architecture"],
            "cpu": checked["cpu"], "compiler": checked["compiler"], "python": checked["python"],
        },
        "primary_x86": {
            "host_id": None, "code_sha": None, "environment_sha256": None, "native_module": None,
            "compiler": None, "actual_compile_flags": None, "frequency": None, "affinity": None,
            "actual_pmu_events": None, "reason": "no qualified target-host receipt on this branch",
        },
        "approval": {"G0": "BLOCKED", "G1": "BLOCKED", "G2": "BLOCKED",
                     "A_signoff": None, "E_signoff": None, "V01_accepted": 0, "G3": "BLOCKED"},
    }
    put(output / "protocol_lock.json", lock)
    hashes = output / "P12-SHA256SUMS"
    with hashes.open("x", encoding="utf-8") as out:
        for path in sorted(output.rglob("*")):
            if path.is_file() and path != hashes:
                out.write(f"{sha(path.read_bytes())}  {path.relative_to(output)}\n")
    print("BLOCKED", len(groups), 31, len(c01), len(v01), len(ledger), len(diagnostics), flush=True)


if __name__ == "__main__":
    build(*(Path(arg).resolve() for arg in sys.argv[1:4]))

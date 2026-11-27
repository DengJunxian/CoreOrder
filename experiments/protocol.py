"""Validate frozen R4 inputs and the separately approved execution identity."""

import json
import hashlib
import math
import random
import re
from pathlib import Path

from coreorder.config import ROOT, incremental_workload, json_bytes, load_workload, sha256
from coreorder.contracts import CONTRACT_VERSION
from coreorder.schema import validate_record
from validation.codec import digest
from validation.io import read

DEFAULT = ROOT / "configs/experiments"
LISTS = ("C01", "V01", "timing", "E05")
SETTINGS = ("backend", "book_restore", "layout", "workers", "grain", "schedule")
RESEARCH = "A_AUTHORIZED_RESEARCH"
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def within(directory, relative):
    path = (directory / relative).resolve()
    require(not Path(relative).is_absolute() and path.is_relative_to(directory), f"invalid protocol path {relative}")
    return path


def condition(workload, row, runtime):
    return {
        **runtime, "input_hash": workload["input_sha256"], "canonical_input_hash": workload["canonical_input_hash"],
        "effective_config_hash": workload["effective_sha256"][row["settings"]["book_restore"]],
        "seed": row["seed"], "numeric_mode": "libm", **row["settings"],
    }


def order_seed(master, block):
    return int(sha256(f"{master}/{block}".encode())[:13], 16)


class Protocol:
    def __init__(self, directory=DEFAULT):
        self.directory = Path(directory).resolve()
        self.plan = read(self.directory / "frozen.json")
        self.lock = read(self.directory / "protocol_lock.json")
        self.identity = sha256(json_bytes({
            name: file_hash(self.directory / name) for name in ("frozen.json", "protocol_lock.json")
        }))
        require(self.plan["contract_version"] == self.lock["contract_version"] == CONTRACT_VERSION,
                "wrong protocol contract")
        require(type(self.plan["runnable"]) is bool and type(self.lock["locked_for_execution"]) is bool and
                (self.plan["status"], self.plan["runnable"], self.lock["state"], self.lock["locked_for_execution"])
                in (("BLOCKED", False, "BLOCKED", False), ("PASS", True, "PASS", True),
                    (RESEARCH, True, RESEARCH, True)), "inconsistent execution authorization state")
        self.research = self.plan["status"] == RESEARCH
        self.active = self.plan["runnable"] is True
        files = self.lock["candidate_files_sha256"]
        required = {"frozen.json", "figures.json", *(f"runlist-{key}.jsonl" for key in LISTS)}
        require(required <= files.keys(), "lock omits protocol files")
        for relative, expected in files.items():
            require(file_hash(within(self.directory, relative)) == expected, f"protocol digest mismatch: {relative}")
        self.figures = read(self.directory / "figures.json")["figures"]
        self.workloads = self.read_workloads()
        self.rows = {name: [json.loads(line) for line in (self.directory / f"runlist-{name}.jsonl")
                            .read_text().splitlines()] for name in LISTS}
        self.index = {}
        self.groups = {group["id"]: group for group in self.plan["pairing_groups"]}
        self.check_rows()
        self.check_schedule()

    def read_workloads(self):
        results = {}
        for key, item in self.plan["workloads"].items():
            path = within(ROOT, item["path"])
            raw = path.read_bytes()
            settings = load_workload(raw)
            validate_record("workload", settings)
            require(sha256(raw) == item["input_sha256"] == item["effective_sha256"]["upstream"],
                    f"input digest mismatch: {key}")
            effective = (json.dumps(incremental_workload(settings), ensure_ascii=False, allow_nan=False) + "\n").encode()
            require(sha256(effective) == item["effective_sha256"]["incremental"], f"effective digest mismatch: {key}")
            if path.is_relative_to(self.directory):
                name = path.relative_to(self.directory).as_posix()
                require(self.lock["candidate_files_sha256"].get(name) == item["input_sha256"],
                        f"workload absent from lock: {key}")
            results[key] = {**item, "canonical_input_hash": digest(settings), "file": path}
        return results

    def check_rows(self):
        expected = {"C01": self.plan["C01_count"], "V01": self.plan["V01_oracles_required"] +
                    self.plan["V01_candidate_receipts_required"], "timing": self.plan["timing_attempts"],
                    "E05": self.plan["E05_rows"]}
        allowed = {"C01": {"C01"}, "V01": {"V01"}, "timing": {"E01", "H01", "E02", "E03"},
                   "E05": {"E05-profile", "E05-PMU", "E05-replay"}}
        official_seeds = self.plan["formal_seeds"]
        require(len(official_seeds) == len(set(official_seeds)) and len(official_seeds) == 5,
                "formal plan requires five distinct seeds")
        require(self.plan["timing_repeats_per_seed"] == 3 and self.plan["warmups_per_variant"] == 2,
                "formal plan requires three paired repetitions and two warmups")
        stats = self.plan["statistics"]
        require(stats["unit"] == "seed" and stats["bootstrap_resamples"] == 10000 and
                stats["confidence_level"] == 0.95 and type(stats["bootstrap_seed"]) is int,
                "invalid frozen statistical rule")
        budgets = self.plan["primary"]["stage_budgets_minutes"]
        required_stages = {"P01", "C01", "V01", "E01", "H01", "E02", "E03", "E05"}
        require(required_stages <= budgets.keys() and all(positive(value) for value in budgets.values()),
                "invalid stage budgets")
        primary = self.plan["primary"]
        require(sum(budgets.values()) == primary["planned_minutes"] and
                positive(primary["rerun_reserve_minutes"]) and
                primary["planned_minutes"] + primary["rerun_reserve_minutes"] == primary["max_minutes"] <= 480,
                "invalid host budget")
        for name, rows in self.rows.items():
            require(len(rows) == expected[name], f"incorrect {name} row count")
            for row in rows:
                key, settings = row["id"], row["settings"]
                require(isinstance(key, str) and TOKEN.fullmatch(key) and key not in self.index, f"invalid row id {key}")
                require(row["phase"] in allowed[name] and row["workload"] in self.workloads, f"invalid phase/workload: {key}")
                require(type(row["seed"]) is int and row["seed"] in official_seeds, f"invalid seed: {key}")
                require(set(settings) == set(SETTINGS), f"invalid settings keys: {key}")
                validate_record("run_config", {**settings, "seed": row["seed"]})
                if settings["backend"] == "native-parallel":
                    require(settings["grain"] is not None and settings["schedule"] is not None,
                            f"native parallel defaults must be frozen explicitly: {key}")
                maximum = 180 if name == "V01" else 60 if row["phase"] == "E05-profile" else 30
                require(positive(row["timeout_s"]) and row["timeout_s"] <= maximum, f"invalid timeout: {key}")
                require(row["status"] == "NOT_RUN" and row["run_id"] is None and type(row["runnable"]) is bool,
                        f"runlist embeds runtime state: {key}")
                require(self.active or not row["runnable"], f"blocked plan has executable row: {key}")
                self.index[key] = row
                if name not in ("C01", "V01"):
                    continue
                if row.get("runner") == "verified vendor oracle":
                    require(settings["backend"] == "py-seq" and settings["book_restore"] == "upstream",
                            f"invalid independent oracle: {key}")
                    continue
                reference = self.index.get(row["reference"])
                require(reference is not None and reference.get("runner") == "verified vendor oracle" and
                        reference["phase"] == row["phase"] and reference["seed"] == row["seed"] and
                        self.same_input(row, reference), f"invalid or out-of-order reference: {key}")
        require(sum(is_oracle(row) for row in self.rows["V01"]) == self.plan["V01_oracles_required"],
                "incorrect V01 oracle count")

    def same_input(self, left, right):
        return self.workloads[left["workload"]]["input_sha256"] == self.workloads[right["workload"]]["input_sha256"]

    def check_schedule(self):
        groups = self.plan["pairing_groups"]
        require(len(groups) == len(self.groups), "duplicate pairing group")
        for group in groups:
            variants = group["variants"]
            by_id = {v["id"]: {key: v[key] for key in SETTINGS} for v in variants}
            require(len(by_id) == len(variants) and all(left in by_id and right in by_id and left != right
                    for left, right in group["ordered_pairs"]), f"invalid variants in {group['id']}")
            for left, right in group["ordered_pairs"]:
                if group["experiment"] in ("H01", "E03"):
                    key = "book_restore" if group["experiment"] == "H01" else "layout"
                    require({k for k in SETTINGS if by_id[left][k] != by_id[right][k]} == {key},
                            f"uncontrolled {group['experiment']} comparison")
            if group["experiment"] in ("E02", "E03"):
                require(all(row["book_restore"] == "incremental" for row in variants), "uncontrolled order book")
        expected = []
        for group in groups:
            warmups = self.plan["warmup_seeds"]
            require(len(warmups) == self.plan["warmups_per_variant"] and set(warmups) <= set(self.plan["formal_seeds"]),
                    "invalid warmup seeds")
            for variant in group["variants"]:
                expected.extend((group, variant["id"], seed, repeat, True, None, None, None)
                                for repeat, seed in enumerate(warmups, 1))
            expected.extend(self.blocks(group, self.plan["formal_seeds"], self.plan["timing_repeats_per_seed"]))
        require(len(expected) == len(self.rows["timing"]), "timing schedule has missing or extra rows")
        for row, (group, variant, seed, repeat, warmup, block, rng, position) in zip(self.rows["timing"], expected):
            expected_keys = (group["id"], group["workload"], group["experiment"], variant, seed, repeat, warmup,
                             block, rng, position)
            keys = ("group", "workload", "phase", "variant", "seed", "repeat", "warmup",
                    "block_id", "order_seed", "order_position")
            require(tuple(row[key] for key in keys) == expected_keys, f"invalid pairing/order for {row['id']}")
            settings = next(v for v in group["variants"] if v["id"] == variant)
            ref = self.index[row["v01"]]
            require(row["settings"] == {key: settings[key] for key in SETTINGS} == ref["settings"] and
                    ref["phase"] == "V01" and not is_oracle(ref) and row["seed"] == ref["seed"] and
                    self.same_input(row, ref), f"incorrect V01 binding: {row['id']}")

    def blocks(self, group, seeds, repeats):
        for seed in seeds:
            for repeat in range(1, repeats + 1):
                block = f"{group['id']}-{seed}-{repeat}"
                order = order_seed(self.plan["order_master_seed"], block)
                variants = [item["id"] for item in group["variants"]]
                random.Random(order).shuffle(variants)
                for position, variant in enumerate(variants, 1):
                    yield group, variant, seed, repeat, False, block, order, position

    def approval(self, runtime):
        require(self.active, "G3 BLOCKED: formal execution and formal analysis require an effective G3 lock")
        approval, target = self.lock["approval"], self.lock["primary_x86"]
        if self.research:
            require(all(approval[key] == "BLOCKED" for key in ("G0", "G1", "G2", "G3"))
                    and approval["A_signoff"] is None and approval["E_signoff"] is None,
                    "independent research must preserve original team gate status")
        else:
            require(all(approval[key] == "PASS" for key in ("G0", "G1", "G2", "G3")),
                    "G3 prerequisite signoff missing")
        require(runtime["dirty"] is False and runtime["git_sha"] == self.plan["formal_code_sha"] == target["code_sha"] and
                runtime["host_id"] == target["host_id"] and runtime["environment_sha256"] == target["environment_sha256"] and
                runtime["architecture"] in ("x86_64", "AMD64") and runtime["native_sha256"] == target["native_module"]["sha256"]
                and runtime["compiler"] == target["compiler"], "formal source, binary or x86 host identity mismatch")
        require(runtime["schemas_sha256"] == self.lock["baseline_schema_sha256"], "approved record schema differs")
        require(target.get("actual_compile_flags") and target.get("frequency") and target.get("affinity"),
                "target host qualification missing")
        authorization = self.plan["authorized_formal_runs"]
        required = {row["id"] for row in self.rows["timing"]}
        require(isinstance(authorization, list) and len(authorization) == len(set(authorization)) and
                required <= set(authorization) <= required | {row["id"] for row in self.rows["E05"]},
                "incomplete or foreign formal authorization")
        require(all(self.index[row]["runnable"] for row in authorization), "authorized row is not runnable")
        accepted = approval["V01_receipts"]
        v01 = {row["id"] for row in self.rows["V01"] if not is_oracle(row)}
        require(set(accepted) == v01 and approval["V01_accepted"] ==
                self.plan["V01_candidate_receipts_accepted"] == len(v01), "incomplete approved V01 receipts")
        require(all(re.fullmatch(r"[0-9a-f]{32}", value["run_id"]) and
                    re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) for value in accepted.values()) and
                len({value["run_id"] for value in accepted.values()}) == len(v01), "invalid approved V01 identities")
        payload = {
            **self.lock,
            "candidate_files_sha256": {k: v for k, v in self.lock["candidate_files_sha256"].items() if k != "frozen.json"},
            "approval": {k: v for k, v in approval.items() if k not in ("A_signoff", "E_signoff")},
            "execution_plan_sha256": sha256(json_bytes({k: v for k, v in self.plan.items() if k != "protocol_lock_hash"})),
        }
        lock_id = sha256(json_bytes(payload))
        require(self.plan["protocol_lock_hash"] == lock_id, "effective lock digest mismatch")
        if self.research:
            governance = self.lock["research_governance"]
            overlay = Path(__file__).resolve().parents[1]
            expected_tools = {"experiments/protocol.py", "experiments/run.py", "analysis/report.py",
                              "analysis/pmu.py", "analysis/figures.py"}
            require(set(governance["tool_sha256"]) == expected_tools and all(
                file_hash(within(overlay, name)) == digest for name, digest in governance["tool_sha256"].items()
            ), "locked research tooling differs")
            source = within(self.directory, governance["authorization_file"])
            require(file_hash(source) == self.lock["candidate_files_sha256"][governance["authorization_file"]],
                    "research authorization source changed")
            authorization_record = read(source)
            require(governance["regime"] == RESEARCH and governance["original_G3"] == "BLOCKED"
                    and authorization_record["role"] == "A" and authorization_record["reviewer"].strip()
                    and authorization_record["authorization"] == RESEARCH
                    and authorization_record["parent_protocol_lock_hash"] == governance["parent_protocol_lock_hash"]
                    and authorization_record["stages"] == ["timing", "E05"],
                    "independent research authorization mismatch")
            return accepted
        for role in ("A", "E"):
            signoff = approval[f"{role}_signoff"]
            file = within(self.directory, signoff["path"])
            require(file_hash(file) == signoff["sha256"], f"{role} signoff digest mismatch")
            record = read(file)
            require(record["role"] == role and record["status"] == "PASS" and record["reviewer"].strip() and
                    record["protocol_lock_hash"] == lock_id, f"invalid {role} signoff")
        return accepted

    def pilot(self):
        """Use one frozen comparison on a short, existing C01 workload."""
        original = self.groups["E02-W1-SMALL-BATCH"]
        pair = ["native-direct", "native-2"]
        group = {
            **original, "id": "pilot-C01b-normal", "experiment": "P01", "workload": "C01b-normal",
            "ordered_pairs": [pair], "variants": [v for v in original["variants"] if v["id"] in pair],
        }
        seeds = self.plan["pilot_seeds"]
        require(seeds and len(seeds) == len(set(seeds)) and not set(seeds) & set(self.plan["formal_seeds"]),
                "invalid independent pilot seeds")
        common = {"workload": group["workload"], "phase": "P01", "timeout_s": 30}
        rows = []
        for seed in seeds:
            reference = f"pilot-oracle-{seed}"
            rows.append({**common, "id": reference, "seed": seed, "runner": "verified vendor oracle",
                         "settings": {"backend": "py-seq", "book_restore": "upstream", "layout": "not_applicable",
                                      "workers": 1, "grain": None, "schedule": None}})
            for variant in group["variants"]:
                rows.append({**common, "id": f"pilot-validation-{seed}-{variant['id']}", "seed": seed,
                             "reference": reference, "settings": {k: variant[k] for k in SETTINGS},
                             "runner": "candidate"})
        order = [(group, v["id"], seeds[0], 1, True, None, None, None) for v in group["variants"]]
        order.extend(self.blocks(group, seeds, 2))
        for _, variant, seed, repeat, warmup, block, rng, position in order:
            settings = next(v for v in group["variants"] if v["id"] == variant)
            rows.append({**common, "id": f"{block or 'pilot-warmup'}-{variant}", "seed": seed, "repeat": repeat,
                         "group": group["id"], "variant": variant, "warmup": warmup, "block_id": block,
                         "order_seed": rng, "order_position": position,
                         "v01": f"pilot-validation-{seed}-{variant}", "settings": {k: settings[k] for k in SETTINGS}})
        for variant in group["variants"]:
            rows.append({**common, "id": f"pilot-profile-{variant['id']}", "seed": seeds[0], "mode": "profile",
                         "variant": variant["id"], "v01": f"pilot-validation-{seeds[0]}-{variant['id']}",
                         "settings": {k: variant[k] for k in SETTINGS}})
        return rows, group


def is_oracle(row):
    return row.get("runner") == "verified vendor oracle"

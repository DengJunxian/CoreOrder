"""Audit the R5B evidence and render the correctness, configuration and pilot figures."""
import argparse
from collections import Counter, defaultdict
import csv
from hashlib import file_digest, sha256
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "docs/gates/evidence"
PLAN = ROOT / "configs/experiments/r4b"
P11 = ROOT / "docs/roles/A/evidence"
HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def digest(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def csv_rows(path):
    with path.open(newline="", encoding="utf8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("x", encoding="utf8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def verify_sums(path):
    for line in path.read_text().splitlines():
        expected, relative = line.split("  ", 1)
        assert digest(path.parent / relative) == expected, relative


def audit_correctness(plan, lock, stage):
    index_path = EVIDENCE / "R4B" / f"{stage.lower()}-index.json"
    index = read(index_path)
    expected = {row["id"]: row for row in lines(PLAN / f"runlist-{stage}.jsonl")}
    by_case = {row["case_id"]: row for row in index["records"]}
    assert len(by_case) == len(index["records"]) and set(by_case) == set(expected)
    assert len({row["run_id"] for row in by_case.values()}) == len(by_case)
    runtime = index["runtime"]
    target = lock["primary_x86"]
    assert runtime["dirty"] is False
    assert (runtime["git_sha"], runtime["native_sha256"], runtime["host_id"], runtime["environment_sha256"]) == (
        target["code_sha"], target["native_module"]["sha256"], target["host_id"], target["environment_sha256"])
    assert runtime == read(EVIDENCE / "R5A" / "x86-admission.json")["runtime"]
    observed = Counter()
    references = []
    canonical_inputs = {}
    for case, row in by_case.items():
        planned = expected[case]
        workload_id = planned["workload"]
        workload = plan["workloads"][workload_id]
        if workload_id not in canonical_inputs:
            workload_path = ROOT / workload["path"]
            assert digest(workload_path) == workload["input_sha256"]
            canonical = json.dumps(read(workload_path), sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=True, allow_nan=False)
            canonical_inputs[workload_id] = sha256(canonical.encode()).hexdigest()
        assert (row["workload"], row["seed"], row["settings"]) == (
            planned["workload"], planned["seed"], planned["settings"])
        assert row["status"] == "PASS" and not row["censoring"]
        observed[row["oracle"]] += 1
        if row["oracle"]:
            references.append(workload["input_sha256"])
            continue
        receipt = row["receipt"]
        assert (receipt["case_id"], receipt["run_id"]) == (case, row["run_id"])
        ref = by_case[planned["reference"]]
        assert ref["oracle"] and (receipt["reference_case_id"], receipt["reference_run_id"]) == (
            planned["reference"], ref["run_id"])
        assert receipt["identity"] == {
            **runtime, **planned["settings"], "seed": row["seed"], "numeric_mode": "libm",
            "input_hash": workload["input_sha256"],
            "canonical_input_hash": canonical_inputs[workload_id],
            "effective_config_hash": workload["effective_sha256"][planned["settings"]["book_restore"]],
        }
        hashes = [*receipt["evidence"].values(), *receipt["production_final"].values()]
        assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes)
        serialized = json.dumps(receipt, indent=2, allow_nan=False).encode()
        assert sha256(serialized).hexdigest() == row["receipt_sha256"]
        assert index["accepted"][case] == {"run_id": row["run_id"], "sha256": row["receipt_sha256"]}
    if stage == "V01":
        assert index["accepted"] == lock["approval"]["V01_receipts"]
    return {
        "stage": stage, "reference_configs": len(set(references)), "seeds": len({r["seed"] for r in by_case.values()}),
        "oracle_pass": observed[True], "candidate_pass": observed[False], "total_pass": len(by_case),
        "total_planned": len(expected), "scope": "semantic validation; no performance timing",
        "source_index": str(index_path.relative_to(ROOT)), "source_sha256": digest(index_path),
        "source_code_sha": runtime["git_sha"], "host_id": runtime["host_id"],
    }


def pairing_coverage(plan, timing, diagnostics, admission):
    observed = Counter(row["phase"] for row in timing + diagnostics)
    warmups = Counter(row["phase"] for row in timing + diagnostics if row.get("warmup"))
    assert all(row["status"] == "NOT_RUN" and row["run_id"] is None and not row["runnable"]
               for row in timing + diagnostics)
    for phase, count in observed.items():
        state = admission["phases"][phase]
        assert count == state["planned"] == state["not_run"] and warmups[phase] == state["warmup"]
        assert state["valid"] == state["failed"] == state["timeout"] == 0
    blocked = defaultdict(dict)
    for row in timing:
        if row["warmup"]:
            continue
        block = blocked[row["group"]].setdefault((row["seed"], row["repeat"], row["block_id"]), {})
        assert row["variant"] not in block
        block[row["variant"]] = row["order_position"]
    rows = []
    seeds = plan["formal_seeds"]
    repeats = plan["timing_repeats_per_seed"]
    expected = {(seed, repeat) for seed in seeds for repeat in range(1, repeats + 1)}
    for group in plan["pairing_groups"]:
        blocks = blocked[group["id"]]
        assert len(blocks) == len(expected) and {(seed, repeat) for seed, repeat, _ in blocks} == expected
        variants = {entry["id"] for entry in group["variants"]}
        assert all(set(block) == variants and set(block.values()) == set(range(1, len(variants) + 1))
                   for block in blocks.values())
        for baseline, challenger in group["ordered_pairs"]:
            assert {baseline, challenger} <= variants
            rows.append({
                "phase": group["experiment"], "group": group["id"], "workload": group["workload"],
                "baseline": baseline, "variant": challenger, "status": "NOT_RUN",
                "expected_pairs": len(blocks), "valid_pairs": 0, "missing_pairs": len(blocks),
                "expected_seeds": len(seeds), "complete_seeds": 0,
                "baseline_simulation_median_s": "NA", "baseline_simulation_iqr_s": "NA",
                "variant_simulation_median_s": "NA", "variant_simulation_iqr_s": "NA",
                "seed_log_ratios": "NA", "speedup": "NA", "ci95_low": "NA", "ci95_high": "NA",
                "parallel_efficiency": "NA",
            })
    return rows


def replay_values(source_code):
    index = read(HERE / "replay-raw-index.json")
    captured = index["capture_observed"]
    mirror = read(EVIDENCE / "R4B" / "calibration-summary.json")
    observed = [record["metrics"] for record in index["rows"]]
    key = lambda row: (row["rows"], row["backend"], row["layout"])
    assert sorted(observed, key=key) == sorted(mirror, key=key) and len(observed) == 12
    assert captured["git_sha"] == source_code and captured["seed"] == 11
    assert all(record["launch_status"] == "PASS" and record["git_sha"] == source_code
               for record in index["rows"])
    rows = []
    for record in index["rows"]:
        row = record["metrics"]
        assert row["capture_sha256"] == captured["capture_sha256"]
        assert row["native_sha256"] == captured["native_sha256"]
        assert row["repeats"] == 3000 and row["replay_row_evaluations"] == row["rows"] * row["repeats"]
        rows.append({
            "scope": "R4B x86 replay calibration; one seed, one launch per cell",
            **row, "seed": captured["seed"], "nominal_input_output_kib": row["rows"] * (captured["stride"] + 16) / 1024,
            "ns_per_row_evaluation": 1e9 * row["replay_s"] / row["replay_row_evaluations"],
            "raw_path": record["raw_path"], "raw_sha256": record["raw_sha256"], "git_sha": source_code,
        })
    for size in {row["rows"] for row in rows}:
        assert len({row["output_sha256"] for row in rows if row["rows"] == size}) == 1
    return rows


def config_values(plan, lock):
    runtime = read(EVIDENCE / "R4B" / "environment.json")
    target = lock["primary_x86"]
    assert runtime["architecture"] == "x86_64" and runtime["git_sha"] == target["code_sha"]
    host = (EVIDENCE / "R4A" / "host-linux.log").read_text()
    assert all(key in host for key in ("AMD Ryzen AI 7 H 350", "384 KiB", "256 KiB", "8 MiB", "16 MiB"))
    hardware = [
        ("CPU", "AMD Ryzen AI 7 H 350"),
        ("Topology", "8 cores / 16 threads reported by Windows"),
        ("WSL guest affinity", ", ".join(map(str, target["affinity"]["guest_cpus"]))),
        ("Reported cache", "32 KiB L1I, 48 KiB L1D, 1 MiB L2 per core; 16 MiB shared L3"),
        ("Operating system", "Ubuntu 24.04.5 LTS under Windows 11 / WSL2"),
        ("Language and compiler", f"CPython {runtime['python']}; GCC 13.3.0 (Release)"),
        ("Floating point", ", ".join(target["actual_compile_flags"])),
        ("External threads", "OpenMP and BLAS = 1"),
        ("Native parallel", "1 / 2 / 4 workers; static; grain 128 rows"),
    ]
    loads = []
    for key in dict.fromkeys(group["workload"] for group in plan["pairing_groups"]):
        size = plan["workloads"][key]
        loads.append((key, size["N"], " / ".join(map(str, size["M_by_session"])), size["K"],
                      " + ".join(map(str, size["steps_by_session"]))))
    return hardware, loads


def render(out, correctness, hardware, loads, replay, phases, code):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    navy, teal, orange, ink, gray = "#254861", "#087E7D", "#B44C20", "#16283C", "#486078"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "pdf.fonttype": 42,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.labelcolor": ink, "text.color": ink, "legend.frameon": False})

    def save(fig, path):
        fig.savefig(path.with_suffix(".pdf"), metadata={"CreationDate":None,"ModDate":None})
        fig.savefig(path.with_suffix(".png"), dpi=300)
        plt.close(fig)

    def table(ax, labels, rows, widths, bbox):
        ax.axis("off")
        obj = ax.table(cellText=rows, colLabels=labels, cellLoc="left", colLoc="left",
                       colWidths=widths, bbox=bbox)
        obj.auto_set_font_size(False)
        obj.set_fontsize(8.3)
        for (i, j), cell in obj.get_celld().items():
            cell.set_linewidth(0.4)
            cell.set_edgecolor("#DEE8EE")
            cell.set_facecolor(navy if i == 0 else ("#F1F6F8" if i % 2 else "white"))
            if i == 0:
                cell.set_text_props(weight="bold", color="white")

    fig, ax = plt.subplots(figsize=(8, 2.75))
    fig.text(.06,.88,"Exact-trace correctness on the target x86 host", fontsize=15, weight="bold")
    fig.text(.06,.775,"Independent PAMS reference, ordered events, state checkpoints, ledger and RNG", color=gray)
    table(ax, ["Suite", "Input configs", "Seeds", "Oracle passes", "Candidate passes", "Total passed"],
          [[r[k] for k in ("stage","reference_configs","seeds","oracle_pass","candidate_pass")] +
           [f"{r['total_pass']}/{r['total_planned']}"] for r in correctness],
          [.10,.17,.09,.19,.22,.16], [0,.24,1,.45])
    fig.text(.06,.13,f"R4B source {code[:12]}; 565 validation attempts in total. Counts refer to runs.", fontsize=8.5, color=gray)
    fig.text(.06,.07,"The scope is semantic validation. Run IDs and sealed evidence are listed in the C01 and V01 indexes.",
             fontsize=8.2, color=gray)
    fig.subplots_adjust(left=.06,right=.96)
    save(fig, out/"validation/correctness")

    fig, (ax, bx) = plt.subplots(2, figsize=(8.25,6.1), gridspec_kw={"height_ratios":[3,1.75]})
    fig.text(.06,.935,"Target hardware and retained experiment configurations",fontsize=14.5,weight="bold")
    fig.text(.06,.89,f"R4B candidate, source {code[:12]} · 25 V01 conditions × 5 seeds · 0 formal observations",
             fontsize=8.8,color=gray)
    table(ax, ["Hardware / software", "Recorded setting"], hardware, [.25,.75],[0,0,1,1])
    table(bx, ["Workload", "Agents (N)", "Quotas (M)", "Markets (K)", "Steps by session"],
          loads, [.34,.15,.17,.15,.19],[0,0,1,1])
    fig.text(.06,.035,"M denotes the quota per session. W0-H and W0-CI2002 share identical input bytes.",
             fontsize=8.2,color=gray)
    fig.subplots_adjust(top=.852,bottom=.089,left=.06,right=.96,hspace=.18)
    save(fig,out/"validation/configuration")

    fig, ax = plt.subplots(figsize=(7.7,4.15))
    for backend, label, style in (("native-serial","Direct","-"),("native-parallel","Pool, 4 workers","--")):
        for layout, marker, color in (("aos","o",navy),("soa","s",orange)):
            points = sorted((r for r in replay if r["backend"]==backend and r["layout"]==layout),key=lambda row:row["rows"])
            ax.plot([p["nominal_input_output_kib"] for p in points],[p["ns_per_row_evaluation"] for p in points],
                    marker=marker, color=color, linestyle=style, label=f"{label} / {layout.upper()}")
    ax.set_xticks([256,512,1024])
    ax.set_xlabel("Nominal input + one output (KiB)")
    ax.set_ylabel("Elapsed replay time per row evaluation (ns)")
    ax.legend(ncol=2,loc="upper right",fontsize=8.3)
    ax.grid(axis="y",alpha=.25)
    fig.text(.12,.91,"FCN replay calibration on the target x86 host",fontsize=14.6,weight="bold")
    fig.text(.12,.852,"PILOT · W2-H seed 11 · 12 launches, 1 per point",fontsize=9,color=teal)
    fig.text(.12,.08,"Each launch makes 3,000 binding calls with a real captured prefix. Time includes output allocation and executor wait.",fontsize=8,color=gray)
    fig.text(.12,.032,"SoA column preparation is outside the timer. Prefix size gives nominal storage only.",fontsize=8,color=gray)
    fig.subplots_adjust(top=.80,bottom=.22,left=.12,right=.95)
    save(fig,out/"pilot/replay-calibration")

    phase = {(r["backend"],r["restore"],r["phase"]):r for r in phases}
    fig,(ax,bx)=plt.subplots(1,2,figsize=(9,4.45))
    for i,(backend,restore,color) in enumerate((
        ("py-seq","upstream",navy),("py-seq","incremental",teal),
        ("native-serial","incremental",orange),
    )):
        for j,(metric,marker) in enumerate((("restore_span","o"),("collect","D"))):
            row=phase[backend,restore,metric]
            ax.scatter(float(row["seconds"]), i+(.13 if j else -.13),marker=marker,color=color,s=35)
    ax.scatter([],[],marker="o",color=gray,label="Restore span")
    ax.scatter([],[],marker="D",color=gray,label="Agent selection and decisions")
    ax.legend(loc="center right", bbox_to_anchor=(1, .72), fontsize=7.7)
    ax.set_yticks(range(3),["Python / upstream","Python / incremental","Native direct / incremental"])
    ax.invert_yaxis()
    ax.set_title("A. Restore and decision spans",loc="left",fontsize=10,weight="bold")
    ax.set_xlim(.17,20)
    metrics=(("draw_preparation","Random preparation"),("packing_and_lease","Packing and lease"),
             ("native_binding","Native binding"),("rebuild_and_release","Order rebuild and release"))
    for i,(metric,label) in enumerate(metrics):
        row=phase["native-serial","incremental",metric]
        bx.scatter(float(row["seconds"]),i,color=orange,s=34)
    bx.set_yticks(range(4),[label for _,label in metrics])
    bx.invert_yaxis()
    bx.set_title("B. Direct-native subphases",loc="left",fontsize=10,weight="bold")
    bx.set_xlim(.00055,.5)
    for axis in (ax,bx):
        axis.set_xscale("log")
        axis.grid(axis="x",which="major",alpha=.25)
        axis.set_xlabel("Accumulated instrumented time (s, log scale)")
    fig.text(.21,.91,"Instrumented cost spans in the P11 pilot",fontsize=14.6,weight="bold")
    fig.text(.21,.847,"PILOT · Apple M5 · W1-H seed 11 · 3 instrumented runs",fontsize=9,color=teal)
    fig.text(.04,.075,"Panel A: 1,211 restore spans and 120 decision spans per mode. Panel B: 120 calls per displayed subphase.",
             fontsize=8,color=gray)
    fig.text(.04,.033,"Panel B expands intervals within native agent decisions. Overlapping intervals use separate axes.",
             fontsize=8,color=gray)
    fig.subplots_adjust(top=.775,bottom=.22,left=.21,right=.96,wspace=.74)
    save(fig,out/"pilot/instrumented-spans")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    out = parser.parse_args().output.resolve()
    verify_sums(PLAN / "R4B-SHA256SUMS")
    verify_sums(EVIDENCE / "R5A" / "SHA256SUMS")
    plan, lock = read(PLAN/"frozen.json"), read(PLAN/"protocol_lock.json")
    admission = read(EVIDENCE/"R5A"/"formal-coverage.json")
    assert plan["status"] == lock["state"] == "BLOCKED"
    assert plan["runnable"] is False and lock["locked_for_execution"] is False
    assert plan["authorized_formal_runs"] == [] and plan["protocol_lock_hash"] is None
    assert admission["formal_raw_attempts"] == 0
    assert "Formal runner claims: 0" in (HERE/"x86-inventory.log").read_text()
    correctness = [audit_correctness(plan,lock,stage) for stage in ("C01","V01")]
    timing, diagnostics = (lines(PLAN/f"runlist-{name}.jsonl") for name in ("timing","E05"))
    pairing = pairing_coverage(plan,timing,diagnostics,admission)
    hardware, loads = config_values(plan,lock)
    code = lock["primary_x86"]["code_sha"]
    replay = replay_values(code)
    phases = csv_rows(P11/"P11-phases.csv")
    assert len({row["case"] for row in phases}) == 3 and all(row["seed"]=="11" and row["status"]=="PASS" for row in phases)
    out.mkdir(exist_ok=False, parents=True)
    (out/"validation").mkdir()
    (out/"pilot").mkdir()
    write_csv(out/"formal-pairing-coverage.csv",pairing)
    write_csv(out/"validation/correctness.csv",correctness)
    write_csv(out/"validation/hardware.csv",[dict(field=name,value=value) for name,value in hardware])
    write_csv(out/"validation/workloads.csv",[
        dict(workload=w,agents=n,quotas=m,markets=k,steps=s) for w,n,m,k,s in loads])
    write_csv(out/"pilot/replay-calibration.csv",replay)
    write_csv(out/"pilot/instrumented-spans.csv",phases)
    render(out,correctness,hardware,loads,replay,phases,code)
    print(f"PASS: {sum(r['total_pass'] for r in correctness)} validation records, {len(pairing)} planned comparisons, "
          f"{sum(r['expected_pairs'] for r in pairing)} expected pair slots, 0 observed pairs; {len(replay)} replay calibration launches")


if __name__ == "__main__":
    main()

"""Exercise the local raw-to-figure path without enabling formal experiments."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def collect(output):
    from experiments.capture import execute
    from coreorder.schema import validate_record as shared_schema
    from validation.compare import compare, save_reproducer
    from validation.gate import evaluate_cell
    from validation.invariants import check
    from validation.io import read as read_trace, write
    from validation.records import eligible, validate_record

    output.mkdir()
    raw = output / "raw"
    raw.mkdir()
    config = Path("configs/workloads/native-serial-normal.json").resolve()
    seed = 11
    interpreter = [sys.executable, "-B", "-m"]
    reference = raw / "reference.json.gz"
    command = [*interpreter, "validation", "collect", "--config", str(config),
               "--seed", str(seed), "--pams-root", "vendor/pams", "--output", str(reference)]
    assert execute(command, output / "oracle-command", 30)["status"] == "PASS"
    original = read_trace(reference)
    assert check(original)["status"] == "PASS"

    results = []
    variants = [
        ("py-seq", "upstream", "not_applicable"),
        ("py-seq", "incremental", "not_applicable"),
        ("native-serial", "incremental", "soa"),
    ]
    for backend, heap, layout in variants:
        label = f"{backend}-{heap}-{layout}"
        target = raw / label
        command = [*interpreter, "coreorder", "run", "--config", str(config),
                   "--seed", str(seed), "--output", str(target), "--backend", backend,
                   "--book-restore", heap, "--workers", "1", "--validation-trace"]
        if layout != "not_applicable":
            command.extend(("--layout", layout))
        receipt = execute(command, output / f"{label}-command", 30)
        assert receipt["status"] == "PASS"
        manifest, metrics, status, environment = (
            read(target / f"{name}.json") for name in ("manifest", "metrics", "status", "environment")
        )
        for kind, record in (("manifest", manifest), ("metrics", metrics),
                             ("status", status), ("environment", environment)):
            shared_schema(kind, record)
        assert manifest["git_sha"] == receipt["git_sha"] and manifest["dirty"] is receipt["dirty"] is False
        assert manifest["backend_requested"] == manifest["backend_effective"] == backend
        assert status["run_id"] == manifest["run_id"] and status["status"] == "PASS"
        assert manifest["input_hash"] == sha(config) == sha(target / "workload.json")
        assert manifest["effective_config_hash"] == sha(target / "effective_config.json")
        assert manifest["environment_hash"] == sha(target / "environment.json")
        assert metrics["measurement_mode"] == "diagnostic"
        if environment.get("native_module"):
            binary = environment["native_module"]
            assert sha(Path(binary["path"])) == binary["sha256"]

        trace = read_trace(target / "validation-trace.json.gz")
        structural = compare(original, trace)
        if structural["status"] != "PASS":
            save_reproducer(original, trace, output / f"{label}-first-difference")
            raise AssertionError(label)
        assert check(trace)["status"] == "PASS"
        e_gate = evaluate_cell(original, trace, manifest, status, {
            "backend_effective": backend, "book_restore": heap, "layout": layout, "seed": seed,
        })
        try:
            validate_record(manifest, metrics, status)
            e_records = {"status": "PASS"}
        except ValueError as error:
            e_records = {"status": "FAIL", "reason": str(error)}
        try:
            formal = eligible(manifest, metrics, status)
        except ValueError:
            formal = False
        assert formal is False
        result = {
            "run_id": manifest["run_id"], "git_sha": manifest["git_sha"], "seed": seed,
            "raw_path": target.relative_to(output).as_posix(), "command_status": receipt["status"],
            "hashes": {name: sha(target / name) for name in ("manifest.json", "metrics.json", "status.json",
                                                            "effective_config.json", "validation-trace.json.gz")},
            "shared_schema": "PASS", "structural": structural, "E_gate": e_gate,
            "E_records": e_records, "formal_eligible": formal,
            "manifest_input_hash": manifest["input_hash"], "reference_config_hash": original["input_hash"],
            "native_module": environment["native_module"],
        }
        results.append(result)
        print(label, manifest["run_id"], structural["status"], e_gate, e_records, flush=True)
    write(output / "lineage.json", {"scope": "P12 development diagnostics only", "runs": results,
                                    "reference_sha256": sha(reference)})


def plot(output):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.ticker import MaxNLocator

    lineage = read(output / "lineage.json")
    rows = []
    for link in lineage["runs"]:
        assert link["formal_eligible"] is False and link["structural"]["status"] == "PASS"
        raw = output / link["raw_path"]
        assert all(sha(raw / file) == digest for file, digest in link["hashes"].items())
        manifest = read(raw / "manifest.json")
        metrics = read(raw / "metrics.json")
        status = read(raw / "status.json")
        assert manifest["run_id"] == status["run_id"] == link["run_id"]
        assert status["status"] == "PASS" and metrics["measurement_mode"] == "diagnostic"
        rows.append({
            "run_id": link["run_id"], "git_sha": link["git_sha"], "seed": link["seed"],
            "backend": manifest["backend_effective"], "heap": manifest["book_restore"],
            "layout": manifest["layout"], "raw_path": link["raw_path"], "source_metrics_sha256": sha(raw / "metrics.json"),
            "orders": metrics["orders"], "executions": metrics["executions"], "expirations": metrics["expirations"],
            "E_gate": link["E_gate"]["status"], "formal_eligible": False,
        })

    table = output / "plot-data.csv"
    with table.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), layout="constrained")
    labels = [f'{row["backend"]}\n{row["heap"]}' + (f' / {row["layout"]}' if row["layout"] != "not_applicable" else "")
              for row in rows]
    for ax, field in zip(axes, ("orders", "executions", "expirations"), strict=True):
        values = [row[field] for row in rows]
        assert len(set(values)) == 1
        bars = ax.bar(range(len(rows)), values, color=["#315e82", "#5884a6", "#458584"], width=0.67)
        ax.bar_label(bars, padding=3)
        ax.set_title(field.capitalize())
        ax.set_ylim(0, max(values) * 1.25)
        ax.set_xticks(range(len(rows)), labels, fontsize=8)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("P12 raw-to-figure check  |  Diagnostic only", fontsize=15, fontweight="bold")
    fig.supxlabel(f'Seed {rows[0]["seed"]} · source {rows[0]["git_sha"][:12]} · formal records ineligible', fontsize=10)
    figure = output / "diagnostic-workload.png"
    assert not figure.exists()
    fig.savefig(figure, dpi=170)
    with (output / "figure-receipt.json").open("x", encoding="utf-8") as handle:
        json.dump({"image_sha256": sha(figure), "table_sha256": sha(table), "matplotlib": matplotlib.__version__,
                   "python": sys.version, "python_path": sys.executable, "run_ids": [row["run_id"] for row in rows]},
                  handle, indent=2)
    print(figure, sha(figure), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("collect", "plot"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    (collect if args.mode == "collect" else plot)(args.output.resolve())

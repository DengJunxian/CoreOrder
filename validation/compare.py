"""Structural first-divergence and portable reproducer, not hash-only equality.

SPDX-License-Identifier: EPL-1.0
"""
import json
from pathlib import Path


def first_diff(left, right, path="$"):
    if type(left) is not type(right):
        return {"path": path, "reference": left, "candidate": right, "reason": "type"}
    if isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                return {"path": path + "/" + key, "reference": left.get(key),
                        "candidate": right.get(key), "reason": "missing_key"}
            diff = first_diff(left[key], right[key], path + "/" + key)
            if diff:
                return diff
    elif isinstance(left, list):
        for i, (a, b) in enumerate(zip(left, right)):
            diff = first_diff(a, b, path + f"/{i}")
            if diff:
                return diff
        if len(left) != len(right):
            return {"path": path + f"/{min(len(left),len(right))}", "reason": "length",
                    "reference": len(left), "candidate": len(right)}
    elif left != right:
        return {"path": path, "reference": left, "candidate": right, "reason": "value"}
    return None


def compare(reference, candidate):
    # Identity must match BEFORE semantic arrays can be compared.
    for key in ("contract_version", "upstream_sha", "input_hash", "seed"):
        if key not in reference or key not in candidate or reference[key] != candidate[key]:
            return {"status": "FAIL", "scope": "identity", "difference": {"path": key,
                    "reference": reference.get(key), "candidate": candidate.get(key)}}
    for scope in ("events", "steps", "final", "rng"):
        if scope not in reference or scope not in candidate:
            return {"status": "FAIL", "scope": scope, "difference": {"reason": "missing_scope"}}
        diff = first_diff(reference[scope], candidate[scope])
        if diff:
            report = {"status": "FAIL", "scope": scope, "difference": diff}
            if scope in ("events", "steps"):
                index = int(diff["path"].split("/")[1])
                report["index"] = index
                row = reference[scope][index] if index < len(reference[scope]) else candidate[scope][index]
                report["location"] = {k: row.get(k) for k in ("session", "step", "next_market_times") if k in row}
                report["context"] = {"reference": reference[scope][max(0,index-1):index+2],
                                     "candidate": candidate[scope][max(0,index-1):index+2]}
            return report
    return {"status": "PASS", "scopes": ["events", "steps", "final", "rng"]}


def save_reproducer(reference, candidate, directory, reference_path=None, candidate_path=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    report = compare(reference, candidate)
    from .io import write
    for name, value in [("reference.json.gz", reference), ("candidate.json.gz", candidate),
                        ("config.json", reference["config"])]:
        write(directory / name, value)
    report.update({"seed": reference["seed"], "upstream_sha": reference["upstream_sha"],
                   "reference_origin": reference_path, "candidate_origin": candidate_path,
                   "replay_command": f'python -m validation replay --bundle "{directory.as_posix()}"',
                   "scope_note": "First divergence context; full input retained, no claim of delta-debug minimality",
                   "rng_context": {"reference": reference["rng"], "candidate": candidate["rng"]}})
    (directory / "first_divergence.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

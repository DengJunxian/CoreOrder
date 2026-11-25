"""R4 run record checks and conservative summary eligibility.

E-owned review implementation; A owns the eventual shared schemas.
SPDX-License-Identifier: EPL-1.0
"""
import json
from pathlib import Path
import re

from . import CONTRACT, PAMS_SHA

STATUSES = {"PASS", "FAIL", "TIMEOUT", "UNSUPPORTED", "NOT_RUN"}
TIMES = ("setup_s", "simulation_s", "process_wall_s", "draw_pack_s", "native_compute_s",
         "rebuild_orders_s", "handle_orders_s", "optional_restore_s")


def validate_record(manifest, metrics, status):
    import jsonschema
    schema = json.loads(Path(__file__).with_name("manifest.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, schema)
    if manifest["contract_version"] != CONTRACT or manifest["upstream_sha"] != PAMS_SHA:
        raise ValueError("Wrong contract or upstream")
    for key in ("status", "validation_status"):
        if status.get(key) not in STATUSES:
            raise ValueError(f"Missing/invalid {key}")
    if status.get("run_id") != manifest["run_id"]:
        raise ValueError("run_id mismatch")
    for key in TIMES:
        if key not in metrics:
            raise ValueError(f"Missing metric {key}; missing is not implicit zero")
        value = metrics[key]
        if value is None:
            if not metrics.get("missing_reasons", {}).get(key):
                raise ValueError(f"Missing reason for {key}")
        elif type(value) not in (int, float) or not 0 <= value < float("inf"):
            raise ValueError(f"Invalid metric {key}")
        elif metrics.get("metric_sources", {}).get(key) not in ("measured", "derived"):
            raise ValueError(f"Unproven/zero-filled metric {key}")
    if status["status"] != "PASS" and metrics["simulation_s"] is not None:
        raise ValueError("Incomplete run cannot have successful simulation time")
    if status["status"] == "TIMEOUT" and status.get("censoring") != "right":
        raise ValueError("TIMEOUT must retain right censoring")
    paired = metrics.get("measurement_mode") == "timing"
    for key in ("block_id", "pairing_group_id", "order_seed", "order_position"):
        if paired and manifest[key] is None:
            raise ValueError("Formal timing requires planned pairing identity")
    if not paired and any(manifest[k] is None for k in ("block_id", "pairing_group_id")):
        if not manifest.get("pairing_not_applicable_reason"):
            raise ValueError("Nonpaired record requires reason")
    return True


def eligible(manifest, metrics, status):
    validate_record(manifest, metrics, status)
    return (status["status"] == status["validation_status"] == "PASS"
            and not manifest["dirty"] and not manifest["warmup"]
            and manifest["backend_requested"] == manifest["backend_effective"]
            and metrics.get("measurement_mode") == "timing"
            and metrics["simulation_s"] is not None and metrics["simulation_s"] > 0
            and bool(re.fullmatch(r"[0-9a-f]{64}", manifest.get("protocol_hash", "")))
            and bool(manifest.get("validation_run_id")))

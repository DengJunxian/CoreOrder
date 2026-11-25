import copy
import json
from pathlib import Path

import pytest

from validation.compare import compare
from validation.reference import collect
from validation.records import TIMES, eligible, validate_record


def test_upstream_repeat_exact(pams_root, small_config):
    left = collect(small_config, 42, pams_root)
    right = collect(small_config, 42, pams_root)
    assert compare(left, right)["status"] == "PASS"
    assert len(left["steps"]) == 7  # initial time update + each business step
    assert any(e["type"] == "OrderLog" for e in left["events"])
    assert "fundamentals/_np_prng" in left["rng"]


def record():
    from validation import PAMS_SHA
    m = dict(run_id="test", experiment_id="C01", workload_id="small", protocol_hash="a"*64,
             git_sha="b"*40, dirty=False, upstream_sha=PAMS_SHA, contract_version="coreorder-r4-v1",
             backend_requested="py-seq", backend_effective="py-seq", book_restore="upstream",
             numeric_mode="libm", layout="not_applicable", workers=1, seed=42, repeat=0,
             warmup=False, host_id="test", input_hash="c"*64, environment_hash="d"*64,
             block_id="b0", pairing_group_id="p0", order_seed=17, order_position=0,
             validation_run_id="v0")
    metrics = {k: None for k in TIMES}
    metrics.update(missing_reasons={k:"not collected" for k in TIMES}, metric_sources={}, measurement_mode="timing")
    status = dict(run_id="test", status="NOT_RUN", validation_status="NOT_RUN")
    return m, metrics, status


@pytest.mark.parametrize("field", ["git_sha", "contract_version", "backend_effective"])
def test_schema_rejects_missing(field):
    m,t,s = record()
    del m[field]
    with pytest.raises(Exception):
        validate_record(m,t,s)


def test_status_and_zero_fill_rejected():
    m,t,s = record()
    del s["status"]
    with pytest.raises(ValueError):
        validate_record(m,t,s)
    m,t,s = record()
    t["simulation_s"] = 0
    with pytest.raises(ValueError, match="zero-filled"):
        validate_record(m,t,s)


def test_unrun_and_fallback_excluded():
    m,t,s = record()
    assert not eligible(m,t,s)
    s.update(status="PASS", validation_status="PASS")
    m.update(backend_requested="native-parallel", backend_effective="py-seq")
    assert not eligible(m,t,s)


def test_missing_timing_excluded_even_if_pass():
    m,t,s=record()
    s.update(status="PASS",validation_status="PASS")
    assert not eligible(m,t,s)
    t["simulation_s"]=0.5
    t["metric_sources"]["simulation_s"]="measured"
    assert eligible(m,t,s)

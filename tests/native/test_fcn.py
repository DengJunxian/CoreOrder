import json
import random
import sys
import time
from threading import Event
import weakref
from concurrent.futures import ThreadPoolExecutor
from importlib.util import find_spec

import numpy as np
import pytest

from coreorder.contracts import CONTRACT_VERSION, INPUT_DTYPE, OUTPUT_DTYPE
from fcn_cases import columns, generated_cases, order_key, public_replay, public_rng, random_state

if find_spec("_coreorder_fcn") is None:
    pytest.skip("build the production FCN extension", allow_module_level=True)

from coreorder.native_serial import load_native_serial

native = load_native_serial()
AGENTS = 112


@pytest.fixture(scope="module")
def live():
    return generated_cases(AGENTS)


def dispatch(evaluator, layout, data):
    return evaluator.aos(data) if layout == "aos" else evaluator.soa(columns(data))


def assert_orders(outputs, inputs, orders, metadata, order_module):
    assert len(outputs) == len(orders)
    for output, row, upstream, context in zip(outputs, inputs, orders, metadata, strict=True):
        agent_id, market_id, call_index = context
        price, side, error = float(output["price"]), int(output["side"]), int(output["error"])
        assert error == 0 and side in {-1, 0, 1}, (context, output)
        actual = ()
        if side:
            actual = (order_key(order_module.Order(
                agent_id=agent_id, market_id=market_id, kind=order_module.LIMIT_ORDER,
                is_buy=side > 0, volume=1, ttl=int(row["window"]), price=price,
            )),)
        else:
            assert price.hex() == "0x0.0p+0", context
        assert actual == upstream, {
            "agent": agent_id, "market": market_id, "call_index": call_index,
            "input": {k: float(row[k]).hex() if INPUT_DTYPE[k].kind == "f" else int(row[k])
                      for k in INPUT_DTYPE.names},
            "upstream": upstream, "native": actual,
        }


def test_candidate_abi():
    assert native.contract_version == CONTRACT_VERSION
    data, _ = public_replay()
    replay = dispatch(native.Evaluator(), "aos", data)
    assert data.dtype.itemsize == 112 and data.dtype.alignment == 8
    assert replay.dtype == OUTPUT_DTYPE and replay.dtype.isalignedstruct
    assert replay.dtype.itemsize == 16 and replay.dtype.alignment == 8
    assert data.strides == (112,) and replay.strides == (16,)
    assert data.flags.aligned and data.ctypes.data % 8 == 0
    assert replay.flags.aligned and replay.ctypes.data % 8 == 0
    assert [INPUT_DTYPE.fields[k][1] for k in INPUT_DTYPE.names] == [*range(0, 105, 8), 108]
    assert [replay.dtype.fields[k][1] for k in replay.dtype.names] == [0, 8, 12]
    for column in columns(data).values():
        assert column.flags.aligned and column.ctypes.data % column.dtype.alignment == 0
        assert column.strides == (column.dtype.itemsize,)


def test_public_rng_replay():
    _, entries = public_replay()
    differences = []
    for entry, saved in zip(entries, public_rng(), strict=True):
        key = (entry["workload"], entry["call_index"])
        assert key == (saved["workload"], saved["call_index"])
        prng = random.Random()
        prng.setstate(random_state(saved["before"]))
        names = ["z_noise"]
        if entry["input"]["margin_type"] == 1:
            names.append("z_margin")
        for name in names:
            actual = prng.gauss(0.0, 1.0).hex()
            expected = entry["input"][name]
            if actual != expected:
                differences.append((*key, name, expected, actual))
        actual, expected = prng.getstate(), random_state(saved["after"])
        assert actual[:2] == expected[:2], key
        actual_cache, expected_cache = [None if state[2] is None else state[2].hex()
                                        for state in (actual, expected)]
        assert (actual_cache is None) == (expected_cache is None), key
        if actual_cache != expected_cache:
            differences.append((*key, "gauss_cache", expected_cache, actual_cache))
    # A captured the public fixture on macOS ARM64. Hex differences in its
    # libm-derived Gaussian outputs are diagnostic here. Local live calls
    # separately require exact draws and full states on this machine.
    print("PUBLIC_RNG_CROSS_HOST " + json.dumps(differences))


@pytest.mark.parametrize("layout", ("aos", "soa"))
def test_public_orders(layout):
    inputs, entries = public_replay()
    result = dispatch(native.Evaluator(), layout, inputs)
    assert len(result) == len(entries) == 24
    for i, (output, entry) in enumerate(zip(result, entries, strict=True)):
        observed = {"price": float(output["price"]).hex(), "side": int(output["side"]),
                    "error": int(output["error"])}
        assert observed == entry["output"], (i, entry, observed)


@pytest.mark.parametrize("layout", ("aos", "soa"))
def test_live_original(layout, live):
    inputs, orders, metadata, counts, order_module = live
    assert len(inputs) + counts["inaccessible"] == AGENTS * 100
    assert len(inputs) >= 10000
    assert all(counts[k] for k in (
        "margin_0_chart_1", "margin_0_chart_-1", "margin_1_chart_1", "margin_1_chart_-1",
        "normal_empty", "time_zero", "window_zero", "mean_reversion_zero", "prefilled_agents",
        "unclipped_forecast",
    ))
    result = dispatch(native.Evaluator(), layout, inputs)
    with pytest.warns(UserWarning, match="price should be positive"):
        assert_orders(result, inputs, orders, metadata, order_module)
    if layout == "aos":
        print("LIVE_PAMS " + json.dumps({"rows": len(inputs), **counts}, sort_keys=True))


@pytest.mark.parametrize("layout", ("aos", "soa"))
@pytest.mark.parametrize("length", (0, 1, 17))
def test_length_temporary_and_repeated_calls(layout, length):
    inputs, _ = public_replay()
    expected = dispatch(native.Evaluator(), layout, inputs[:length]).tobytes()
    evaluator = native.Evaluator()
    for _ in range(20):
        output = dispatch(evaluator, layout, inputs[:length].copy())
        assert output.tobytes() == expected


def test_held_references_and_concurrent_serial_calls():
    inputs, _ = public_replay()
    evaluator = native.Evaluator()
    expected = evaluator.aos(inputs).tobytes()
    with ThreadPoolExecutor(max_workers=4) as pool:
        calls = [pool.submit(dispatch, evaluator, layout, inputs.copy())
                 for layout in ("aos", "soa") for _ in range(12)]
        assert all(call.result().tobytes() == expected for call in calls)


def misaligned(dtype):
    return np.ndarray((2,), dtype=dtype, buffer=bytearray(1 + 2 * dtype.itemsize), offset=1)


def test_bad_aos():
    data, _ = public_replay()
    fcn = native.Evaluator().aos
    with pytest.raises(TypeError, match="NumPy array"):
        fcn(data.tolist())
    with pytest.raises(ValueError, match="one-dimensional"):
        fcn(data.reshape(2, 12))
    for incorrect in (np.zeros(2, dtype=np.float64), data.astype(INPUT_DTYPE.newbyteorder("S")),
                      data.astype(np.dtype(INPUT_DTYPE.descr))):
        with pytest.raises(ValueError, match="dtype"):
            fcn(incorrect)
    for noncontiguous in (data[::2], data[:2:2], data[::-1]):
        with pytest.raises(ValueError, match="stride"):
            fcn(noncontiguous)
    offset = misaligned(INPUT_DTYPE)
    assert offset.flags.c_contiguous and offset.ctypes.data % 8 == 1
    with pytest.raises(ValueError, match="aligned"):
        fcn(offset)
    data.setflags(align=False)
    with pytest.raises(ValueError, match="aligned"):
        fcn(data)


def test_bad_soa():
    data, _ = public_replay()
    fcn = native.Evaluator().soa
    baseline = columns(data)
    with pytest.raises(TypeError):
        fcn(list(baseline.items()))
    with pytest.raises(ValueError, match="15 contract fields"):
        fcn(baseline | {"extra": baseline["p_now"]})
    wrong_key = baseline.copy()
    wrong_key["extra"] = wrong_key.pop("p_now")
    with pytest.raises(ValueError, match="missing field p_now"):
        fcn(wrong_key)
    for value, message in (
        (baseline["p_now"].astype("f4"), "dtype"),
        (baseline["p_now"].astype(np.dtype("f8").newbyteorder("S")), "dtype"),
        (baseline["p_now"].reshape(2, 12), "one-dimensional"),
        (baseline["p_now"][::2], "stride"),
        (baseline["p_now"][:-1], "length"),
    ):
        with pytest.raises(ValueError, match=message):
            fcn(baseline | {"p_now": value} if message != "length"
                else baseline | {"p_fund": value})
    for name in ("p_now", "window", "margin_type"):
        value = misaligned(INPUT_DTYPE[name])
        assert value.flags.c_contiguous and value.ctypes.data % value.dtype.alignment == 1
        with pytest.raises(ValueError, match="aligned"):
            fcn(baseline | {name: value})


@pytest.mark.parametrize("layout", ("aos", "soa"))
def test_numeric_error_order(layout):
    data, _ = public_replay()
    data["z_noise"][2] = np.nan
    data["margin_type"][7] = 77
    evaluator = native.Evaluator()
    with pytest.raises(ValueError, match=r"FCN row 2 failed with error 3"):
        dispatch(evaluator, layout, data)
    data["z_noise"][2] = 0
    with pytest.raises(ValueError, match=r"FCN row 7 failed with error 2"):
        dispatch(evaluator, layout, data)
    data["p_now"][0] = 0
    with pytest.raises(ValueError, match=r"FCN row 0 failed with error 1"):
        dispatch(evaluator, layout, data)


def test_normal_empty_candidate_and_overflow():
    data, _ = public_replay()
    row = data[:1].copy()
    row["window"] = row["effective_window"] = 0
    row["p_then"] = row["p_now"]
    row["margin_type"], row["order_margin"], row["z_margin"] = 1, 1000, -1
    evaluator = native.Evaluator()
    with pytest.raises(ValueError, match="error 1"):
        evaluator.aos(row)
    row["window"] = 10000
    row["noise_scale"], row["z_noise"] = 1e300, 1e300
    with pytest.raises(ValueError, match="error 3"):
        evaluator.aos(row)


def test_invalid_parameters_and_serial_route():
    for kwargs in ({"workers": 0}, {"workers": -1}, {"workers": 2}, {"grain": 0}, {"schedule": "other"}):
        with pytest.raises(ValueError):
            native.Evaluator(**kwargs)
    before = native.executor_creations()
    inputs, _ = public_replay()
    native.Evaluator().aos(inputs)
    assert native.executor_creations() == before


@pytest.mark.parametrize("layout", ("aos", "soa"))
@pytest.mark.parametrize("schedule", ("static", "dynamic"))
@pytest.mark.parametrize("workers", (1, 2, 4))
def test_production_parallel(layout, schedule, workers, live):
    inputs, _, _, _, _ = live
    expected = native.Evaluator().aos(inputs).tobytes()
    before = native.executor_creations()
    evaluator = native.Evaluator(parallel=True, workers=workers, grain=117, schedule=schedule)
    assert native.executor_creations() == before + 1
    assert dispatch(evaluator, layout, inputs[:0]).size == 0
    for _ in range(2):
        assert dispatch(evaluator, layout, inputs).tobytes() == expected
    assert native.executor_creations() == before + 1

    invalid = inputs[:300].copy()
    invalid["margin_type"][120] = 99
    invalid["p_now"][4] = np.inf
    with pytest.raises(ValueError, match=r"FCN row 4 failed with error 3"):
        dispatch(evaluator, layout, invalid)


def test_production_parallel_releases_gil_and_keeps_column_owners():
    inputs, _ = public_replay()
    rows = np.tile(inputs, 20000)
    expected = native.Evaluator().aos(rows).tobytes()
    evaluator = native.Evaluator(parallel=True, workers=1, grain=512)
    data = columns(rows)
    owners = [weakref.ref(column) for column in data.values()]
    entered = Event()

    def evaluate():
        def observe(frame, event, value):
            if event == "c_call" and getattr(value, "__name__", None) == "soa":
                entered.set()
        sys.setprofile(observe)
        try:
            return evaluator.soa(data)
        finally:
            sys.setprofile(None)

    previous = sys.getswitchinterval()
    try:
        # Schedule the waiting thread at the binding's explicit GIL release.
        sys.setswitchinterval(1.0)
        with ThreadPoolExecutor(max_workers=1) as pool:
            job = pool.submit(evaluate)
            assert entered.wait(timeout=5)
            time.sleep(0.002)
            assert not job.done(), "binding did not allow Python progress during native execution"
            data.clear()
            assert all(owner() is not None for owner in owners)
            with pytest.raises(RuntimeError, match="already running"):
                evaluator.aos(inputs[:1])
            assert job.result(timeout=10).tobytes() == expected
    finally:
        sys.setswitchinterval(previous)
    assert all(owner() is None for owner in owners)

"""Diagnostic run artifacts shared by the production and upstream entry points."""

import sys
import traceback
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime

from .config import ROOT, json_bytes, load_workload, sha256
from .environment import environment
from .snapshot import PamsObservations, final_rng, final_state


def run_recorded(args, execute, *, entry_point):
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        print(f"cannot create run directory {args.output}: {error.strerror}", file=sys.stderr)
        return 1

    protocol = {
        "version": "P02",
        "measurement_mode": "diagnostic",
        "account_scope": "initial and final",
        "step_scope": "PAMS MarketStepEndLog, before the after-step hook and clock advance",
        "timing_scope": "PAMS run with diagnostic observation enabled",
    }
    run_id = uuid.uuid4().hex
    manifest = {
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "entry_point": entry_point,
        "experiment_id": "P02",
        "workload_id": args.config.stem,
        "protocol_version": protocol["version"],
        "protocol": protocol,
        "protocol_hash": sha256(json_bytes(protocol)),
        "seed": args.seed,
        "repeat": 0,
        "warmup": False,
        "validation_run_id": None,
        "backend_requested": args.backend,
        "backend_effective": None,
        "book_restore": args.book_restore,
        "numeric_mode": "libm",
        "layout": args.layout or "not_applicable",
        "workers": args.workers,
        "grain": args.grain,
        "schedule": args.schedule,
        "block_id": None,
        "pairing_group_id": None,
        "order_seed": None,
        "order_position": None,
        "pairing_not_applicable_reason": "standalone diagnostic run",
    }
    status = {
        "run_id": run_id,
        "status": "FAIL",
        "validation_status": "NOT_RUN",
        "reference_run_id": None,
        "comparison_scope": None,
    }
    metrics = {"measurement_mode": "diagnostic"}
    unmeasured = {
        "setup_s": "phase duration unavailable through this entry point",
        "simulation_s": "phase duration unavailable through this entry point",
        "process_wall_s": "requires a parent process",
        "draw_pack_s": "no phase instrumentation",
        "native_compute_s": "no phase instrumentation",
        "rebuild_orders_s": "no phase instrumentation",
        "handle_orders_s": "no phase instrumentation",
        "optional_restore_s": "no phase instrumentation",
        "agent_calls": "upstream runner is uninstrumented",
        "decision_rows": "upstream runner is uninstrumented",
        "gauss_api_calls": "upstream random streams are uninstrumented",
        "batch_widths": "upstream runner is uninstrumented",
        "rss_bytes": "not collected",
        "pmu": "not collected",
    }
    for key in ("orders", "cancels", "expirations", "executions", "market_steps", "native_rows"):
        unmeasured[key] = "simulation did not complete"
    metrics.update(dict.fromkeys(unmeasured))
    exit_code = 1
    output = args.output
    status_path = output / "status.json"
    status_path.write_bytes(json_bytes({**status, "status": "NOT_RUN"}))

    with (output / "stdout.log").open("w") as stdout, (output / "stderr.log").open("w") as stderr:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                raw = args.config.read_bytes()
                (output / "workload.json").write_bytes(raw)
                manifest["input_hash"] = sha256(raw)
                load_workload(raw)
                effective = output / "effective_config.json"
                effective.write_bytes(raw)
                manifest["effective_config_hash"] = manifest["input_hash"]

                env = environment()
                env_bytes = json_bytes(env)
                (output / "environment.json").write_bytes(env_bytes)
                manifest.update({key: env[key] for key in ("git_sha", "dirty", "host_id", "contract_version")})
                manifest["environment_hash"] = sha256(env_bytes)
                upstream = env["upstream"]
                manifest["upstream_sha"] = upstream["PAMS"]["sha"]
                manifest["upstream_shas"] = {name: item["sha"] for name, item in upstream.items()}

                if args.seed < 0 or args.workers < 1 or (args.grain is not None and args.grain < 1):
                    raise ValueError("seed must be nonnegative, and workers and grain must be positive")
                if args.backend != "py-seq":
                    raise NotImplementedError(f"backend {args.backend!r} is not implemented")
                if args.book_restore != "upstream":
                    raise NotImplementedError(f"book restore {args.book_restore!r} is not implemented")
                if args.layout or args.workers != 1 or args.grain is not None or args.schedule is not None:
                    raise NotImplementedError("py-seq supports one worker and no layout, grain or schedule")
                if any(item["dirty"] or item["sha"] != item["required_sha"] for item in upstream.values()):
                    raise ValueError("the upstream checkouts must be clean and match UPSTREAM.lock.json")
                if (
                    env["pams_install_source"] != (ROOT / "vendor/pams").as_uri()
                    or env["pams_version"] != upstream["PAMS"]["required_version"]
                    or not env["pams_distribution_matches_import"]
                ):
                    raise ValueError("PAMS must be installed from the fixed vendor/pams checkout")

                manifest["backend_effective"] = "py-seq"
                with (output / "events.jsonl").open("wb") as events, (output / "market_steps.jsonl").open("wb") as steps:
                    observer = PamsObservations(events, steps, run_id)
                    runner, timings = execute(effective, args.seed, observer)
                simulator = runner.simulator
                state_data = json_bytes({"initial_accounts": observer.initial_accounts, **final_state(simulator)})
                rng_data = json_bytes(final_rng(runner))
                (output / "final_state.json").write_bytes(state_data)
                (output / "final_rng.json").write_bytes(rng_data)
                quotas = [s.max_normal_orders for s in simulator.sessions]
                manifest.update(
                    N=len(simulator.agents),
                    M=quotas[0] if len(set(quotas)) == 1 else None,
                    K=len(simulator.markets),
                    steps=sum(s.iteration_steps for s in simulator.sessions),
                    max_normal_orders_by_session=quotas,
                    measurement_tool="time.perf_counter" if timings else "PAMS SequentialRunner.main",
                )
                metrics.update(timings)
                metrics.update(
                    orders=observer.counts["order"],
                    cancels=observer.counts["cancel"],
                    expirations=observer.counts["expiration"],
                    executions=observer.counts["execution"],
                    market_steps=observer.market_steps,
                    native_rows=0,
                )
                status.update(
                    status="PASS",
                    trace_hash=observer.event_digest.hexdigest(),
                    final_state_hash=sha256(state_data),
                    rng_hash=sha256(rng_data),
                )
                print(f"orders={metrics['orders']} executions={metrics['executions']} market_steps={metrics['market_steps']}")
                exit_code = 0
            except NotImplementedError as error:
                # Errors from an attempted simulation are failures, not backend rejection.
                if manifest["backend_effective"] is None:
                    status["status"] = "UNSUPPORTED"
                    exit_code = 2
                status["reason"] = str(error)
                print(error, file=sys.stderr)
            except Exception as error:
                status["reason"] = f"{type(error).__name__}: {error}"
                traceback.print_exc()

    metrics["unmeasured"] = {key: reason for key, reason in unmeasured.items() if metrics[key] is None}
    (output / "manifest.json").write_bytes(json_bytes(manifest))
    (output / "metrics.json").write_bytes(json_bytes(metrics))
    status_pending = output / ".status.json.tmp"
    status_pending.write_bytes(json_bytes(status))
    status_pending.replace(status_path)
    if exit_code:
        print(f"{status['status']}: {status['reason']} (see {output / 'stderr.log'})", file=sys.stderr)
    else:
        print(f"PASS {run_id}: {metrics['orders']} orders, {metrics['executions']} executions")
    return exit_code

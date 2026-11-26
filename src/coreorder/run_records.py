"""Diagnostic run artifacts shared by the production and upstream entry points."""

import json
import sys
import traceback
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from .config import ROOT, incremental_workload, json_bytes, load_workload, sha256
from .environment import environment
from .market_adapter import CoreOrderMarket
from .native_serial import NativeSerialRunner, load_native_serial
from .runner import upstream_parallel_factory
from .schema import validate_record
from .snapshot import PamsObservations, final_rng, final_state, market_history


def run_recorded(args, execute, *, entry_point, heap_diagnostics=None):
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        print(f"cannot create run directory {args.output}: {error.strerror}", file=sys.stderr)
        return 1

    protocol = {
        "version": "P03",
        "measurement_mode": "diagnostic",
        "account_scope": "initial, each global step boundary and final",
        "step_scope": "first MarketStepEndLog after orders, before any market after-step hook at that step",
        "timing_scope": "PAMS run with diagnostic observation enabled",
    }
    if heap_diagnostics is not None:
        protocol.update(heap_diagnostics=heap_diagnostics.sizes, count_heap_comparisons=heap_diagnostics.comparisons)
    run_id = uuid.uuid4().hex
    native = args.backend in ("native-serial", "native-parallel")
    parallel_native = args.backend == "native-parallel"
    grain = (128 if args.grain is None else args.grain) if parallel_native else args.grain
    schedule = (args.schedule or "static") if parallel_native else args.schedule
    manifest = {
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "entry_point": entry_point,
        "experiment_id": "P03",
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
        "layout": args.layout or ("aos" if native else "not_applicable"),
        "workers": args.workers,
        "grain": grain,
        "schedule": schedule,
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
    if native:
        unmeasured.update(dict.fromkeys(
            ("agent_calls", "decision_rows", "gauss_api_calls", "batch_widths"), "simulation did not complete",
        ))
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
                settings = load_workload(raw)
                validate_record("workload", settings)
                effective = output / "effective_config.json"
                effective.write_bytes(raw)
                manifest["effective_config_hash"] = manifest["input_hash"]

                env = environment()
                upstream = env["upstream"]
                try:
                    if args.seed < 0 or args.workers < 1 or (args.grain is not None and args.grain < 1):
                        raise ValueError("seed must be nonnegative, and workers and grain must be positive")
                    if args.backend in ("py-seq", "native-serial") and args.workers != 1:
                        raise NotImplementedError("serial backends support one worker")
                    if not parallel_native and (grain is not None or schedule is not None):
                        raise NotImplementedError("grain and schedule require native-parallel")
                    if not native and args.layout:
                        raise NotImplementedError("Python backends have no native layout")
                    if any(item["dirty"] or item["sha"] != item["required_sha"] for item in upstream.values()):
                        raise ValueError("the upstream checkouts must be clean and match UPSTREAM.lock.json")
                    if (
                        env["pams_install_source"] != (ROOT / "vendor/pams").as_uri()
                        or env["pams_version"] != upstream["PAMS"]["required_version"]
                        or not env["pams_distribution_matches_import"]
                    ):
                        raise ValueError("PAMS must be installed from the fixed vendor/pams checkout")
                    validate_record("run_config", {
                        "backend": args.backend, "book_restore": args.book_restore,
                        "layout": manifest["layout"], "workers": args.workers,
                        "grain": grain, "schedule": schedule, "seed": args.seed,
                    })
                    if native:
                        module = load_native_serial()
                        if not hasattr(module, "executor_creations"):
                            raise NotImplementedError("build the integrated _coreorder_fcn extension")
                        library = Path(module.__file__).resolve()
                        env["native_module"] = {
                            "path": str(library), "sha256": sha256(library.read_bytes()),
                            "contract_version": module.contract_version,
                        }
                        before_executors = module.executor_creations()
                        options = {"grain": grain, "schedule": schedule} if parallel_native else {}

                        def factory(**kwargs):
                            evaluator = module.Evaluator(parallel=parallel_native, workers=args.workers, **options)
                            return NativeSerialRunner(
                                evaluate=getattr(evaluator, manifest["layout"]), layout=manifest["layout"],
                                market_adapter=CoreOrderMarket if args.book_restore == "incremental" else None,
                                **kwargs,
                            )

                        execute = partial(execute, runner_factory=factory)
                    elif args.backend in ("py-thread", "py-process"):
                        execute = partial(
                            execute, runner_factory=partial(upstream_parallel_factory, args.backend, args.workers),
                        )
                finally:
                    validate_record("environment", env)
                    env_bytes = json_bytes(env)
                    (output / "environment.json").write_bytes(env_bytes)
                    manifest.update({key: env[key] for key in ("git_sha", "dirty", "host_id", "contract_version")})
                    manifest["environment_hash"] = sha256(env_bytes)
                    manifest["upstream_sha"] = upstream["PAMS"]["sha"]
                    manifest["upstream_shas"] = {name: item["sha"] for name, item in upstream.items()}

                if args.book_restore == "incremental":
                    effective_bytes = (
                        json.dumps(incremental_workload(settings), ensure_ascii=False, allow_nan=False) + "\n"
                    ).encode()
                    effective.write_bytes(effective_bytes)
                    manifest["effective_config_hash"] = sha256(effective_bytes)
                trace = getattr(args, "validation_trace", False)
                if trace:
                    from .validation_trace import ObservedSimulator, ValidationObservations
                    observer_type = ValidationObservations
                else:
                    observer_type = PamsObservations
                manifest["backend_effective"] = args.backend
                with (
                    (output / "events.jsonl").open("wb") as events,
                    (output / "market_steps.jsonl").open("wb") as steps,
                    (output / "step_states.jsonl").open("wb") as step_states,
                ):
                    observer = observer_type(events, steps, step_states, run_id)
                    if trace:
                        execute = partial(execute, simulator_class=ObservedSimulator, after_setup=observer.after_setup)
                    runner, timings = execute(effective, args.seed, observer)
                if trace:
                    observer.write_trace(output, settings, args.seed, manifest, runner)
                if args.backend == "py-process":
                    pool = runner.copy_metrics_pool
                    (output / "process_copy.json").write_bytes(json_bytes({
                        "start_method": runner.start_method, "tasks_sent": pool.copied_calls,
                        "serialized_dispatch_bytes": pool.copied_bytes, "dispatch_send_s": pool.send_s,
                        "scope": "parent call queue; pipe send time excludes pickle, receiving and unpickle",
                    }))
                if heap_diagnostics is not None:
                    (output / "heap_diagnostics.json").write_bytes(json_bytes(heap_diagnostics.report()))
                simulator = runner.simulator
                state_data = json_bytes({
                    "initial_accounts": observer.initial_accounts,
                    **final_state(simulator),
                    "market_history": market_history(simulator),
                })
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
                if native:
                    metrics.update(
                        agent_calls=runner.agent_calls, decision_rows=runner.native_rows,
                        native_rows=runner.native_rows, gauss_api_calls=runner.gauss_api_calls,
                        batch_widths=runner.batch_widths,
                        native_executor_creations=module.executor_creations() - before_executors,
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

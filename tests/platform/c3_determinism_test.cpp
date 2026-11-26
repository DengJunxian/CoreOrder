// SPDX-License-Identifier: EPL-1.0
// Member C — Stage C3: Determinism Under Static & Dynamic Partitioners,
// Exception Join Safety, Deterministic Earliest-Range Error Propagation,
// Re-entrancy Rejection, and Nested BLAS Thread Diagnostics.

#include "executor.hpp"
#include "fcn_test_fixture.hpp"

#include <atomic>
#include <chrono>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

void require(bool cond, const std::string& msg) {
    if (!cond) {
        throw std::runtime_error("C3 test FAILED: " + msg);
    }
}

void verify_bit_identical(const std::vector<coreorder::OutputRow>& a,
                          const std::vector<coreorder::OutputRow>& b,
                          const std::string& label) {
    require(a.size() == b.size(), label + ": size mismatch");
    if (!a.empty()) {
        require(std::memcmp(a.data(), b.data(), a.size() * sizeof(coreorder::OutputRow)) == 0,
                label + ": byte-level output mismatch");
    }
}

}  // namespace

int main(int argc, char** argv) {
    using namespace coreorder;
    using namespace coreorder::runtime;
    using namespace coreorder::runtime::test_fixture;

    const std::string fixture_path =
        (argc > 1) ? std::string(argv[1]) : std::string(COREORDER_FIXTURE_PATH);
    const auto base_rows = load_public_fcn_fixture(fixture_path);

    // 1. Static vs Dynamic partitioner determinism across workers=1/2/4/8, grains, AoS & SoA.
    {
        const std::vector<std::size_t> sizes = {0, 1, 24, 127, 128, 129, 1024, 2053};
        const std::vector<std::size_t> grains = {1, 7, 32, 128, 512};
        const std::vector<std::size_t> workers_list = {1, 2, 4, 8};

        for (std::size_t n : sizes) {
            const auto aos_inputs = tile_inputs(base_rows, n);
            const auto soa_storage = pack_soa(aos_inputs);
            const InputView aos_view = AosInputView{aos_inputs.data(), aos_inputs.size()};
            const InputView soa_view = soa_storage.view();

            std::vector<OutputRow> ref_out(n);
            (void)evaluate_serial(
                aos_view, OutputView{ref_out.data(), ref_out.size()}, evaluate_range);

            for (std::size_t w : workers_list) {
                NativeExecutor exec(w);
                for (std::size_t g : grains) {
                    for (Schedule sched :
                         {Schedule::static_partition, Schedule::dynamic_partition}) {
                        std::vector<OutputRow> out_aos(n);
                        std::vector<OutputRow> out_soa(n);
                        std::vector<std::atomic<int>> visits(n);
                        for (std::size_t i = 0; i < n; ++i) {
                            visits[i].store(0, std::memory_order_relaxed);
                        }

                        const auto st_aos = exec.run_ranges(
                            n, g, sched, [&](std::size_t begin, std::size_t end) {
                                for (std::size_t i = begin; i < end; ++i) {
                                    visits[i].fetch_add(1, std::memory_order_relaxed);
                                }
                                evaluate_range(
                                    aos_view, OutputView{out_aos.data(), out_aos.size()}, begin,
                                    end);
                            });
                        for (std::size_t i = 0; i < n; ++i) {
                            require(visits[i].load(std::memory_order_relaxed) == 1,
                                    "exact-once coverage failed for schedule=" +
                                        std::string(to_string(sched)));
                        }
                        verify_bit_identical(
                            ref_out, out_aos,
                            "AoS " + std::string(to_string(sched)) + " w=" + std::to_string(w));

                        const auto st_soa = exec.evaluate_ranges(
                            soa_view, OutputView{out_soa.data(), out_soa.size()}, g, sched,
                            evaluate_range);
                        require(st_aos.rows == n && st_soa.rows == n, "rows stat mismatch");
                        verify_bit_identical(
                            ref_out, out_soa,
                            "SoA " + std::string(to_string(sched)) + " w=" + std::to_string(w));
                    }
                }
            }
        }
        std::cout << "[C3] Verified Static & Dynamic partitioners across workers=1/2/4/8, "
                     "grains=1/7/32/128/512, AoS & SoA bit-for-bit.\n";
    }

    // 2. Exception safety: strict join before rethrow + deterministic earliest-begin exception.
    {
        NativeExecutor exec(4);
        for (Schedule sched : {Schedule::static_partition, Schedule::dynamic_partition}) {
            std::atomic<int> active_tasks{0};
            std::atomic<int> completed_sibling_tasks{0};
            bool caught = false;
            std::string caught_msg;

            try {
                (void)exec.run_ranges(
                    512, 32, sched, [&](std::size_t begin, std::size_t end) {
                        (void)end;
                        active_tasks.fetch_add(1, std::memory_order_acq_rel);
                        struct ExitDecrement {
                            std::atomic<int>& counter;
                            ~ExitDecrement() {
                                counter.fetch_sub(1, std::memory_order_acq_rel);
                            }
                        } dec{active_tasks};

                        if (begin == 128) {
                            // Delays slightly so later chunks throw earlier in wall time;
                            // runtime must still deterministically surface begin==128.
                            std::this_thread::sleep_for(std::chrono::milliseconds(5));
                            throw std::runtime_error("injected_error_at_128");
                        }
                        if (begin == 320) {
                            throw std::runtime_error("injected_error_at_320");
                        }
                        if (begin == 0) {
                            // Slow healthy sibling: must finish BEFORE run_ranges throws.
                            std::this_thread::sleep_for(std::chrono::milliseconds(15));
                        }
                        completed_sibling_tasks.fetch_add(1, std::memory_order_relaxed);
                    });
            } catch (const std::runtime_error& err) {
                caught = true;
                caught_msg = err.what();
                // Critical invariant: ZERO active tasks may remain when exception reaches caller.
                require(active_tasks.load(std::memory_order_acquire) == 0,
                        "sibling worker still active after run_ranges threw!");
            }

            require(caught, "expected injected exception to propagate");
            require(caught_msg == "injected_error_at_128",
                    "expected deterministic earliest-range exception, got: " + caught_msg);
            require(completed_sibling_tasks.load(std::memory_order_relaxed) == 14,
                    "expected all 14 healthy sibling chunks to join cleanly");

            // Executor must remain clean and reusable after a failed batch (in_flight reset).
            std::vector<int> probe(64, 0);
            const auto after_stats = exec.run_ranges(
                probe.size(), 16, sched, [&](std::size_t begin, std::size_t end) {
                    for (std::size_t i = begin; i < end; ++i) {
                        probe[i] = static_cast<int>(i + 1);
                    }
                });
            require(after_stats.task_count == 4, "post-exception reuse task_count mismatch");
            for (std::size_t i = 0; i < probe.size(); ++i) {
                require(probe[i] == static_cast<int>(i + 1), "post-exception reuse output wrong");
            }
        }
        std::cout << "[C3] Verified strict join on exception, deterministic earliest-begin "
                     "exception propagation, and clean post-exception executor state.\n";
    }

    // 3. Re-entrancy rejection test (no deadlock if same executor is called recursively).
    {
        NativeExecutor exec(2);
        bool caught_reentry = false;
        try {
            (void)exec.run_ranges(
                64, 32, Schedule::static_partition, [&](std::size_t begin, std::size_t) {
                    if (begin == 0) {
                        (void)exec.run_ranges(
                            16, 8, Schedule::static_partition,
                            [](std::size_t, std::size_t) {});
                    }
                });
        } catch (const std::runtime_error& err) {
            caught_reentry =
                std::string(err.what()).find("re-entry") != std::string::npos;
        }
        require(caught_reentry, "recursive re-entry on same NativeExecutor must throw");
        std::cout << "[C3] Verified concurrent/recursive re-entry rejection without deadlock.\n";
    }

    // 4. Nested BLAS/OpenMP thread environment audit.
    {
        const auto report = detect_nested_threading_env();
        const auto rec = recommended_single_thread_blas_env();
        require(report.entries.size() == 6 && rec.size() == 6, "nested env audit size");
        std::cout << "[C3] Nested BLAS/OpenMP thread audit (oversubscription_risk="
                  << (report.has_oversubscription_risk ? "true" : "false") << "):\n";
        for (const auto& e : report.entries) {
            std::cout << "     " << e.name << "=" << (e.is_set ? e.value : "<unset>")
                      << " (single_thread=" << (e.is_single_thread ? "true" : "false") << ")\n";
        }
    }

    // 5. Schedule string parser test.
    {
        require(parse_schedule("static") == Schedule::static_partition, "parse static");
        require(parse_schedule("dynamic") == Schedule::dynamic_partition, "parse dynamic");
        bool threw = false;
        try {
            (void)parse_schedule("guided");
        } catch (const std::invalid_argument&) {
            threw = true;
        }
        require(threw, "parse_schedule must reject unsupported schedule");
    }

    std::cout << "[C3] PASS: All determinism, exception-join, re-entrancy, "
                 "and nested-thread checks passed.\n";
    return 0;
}

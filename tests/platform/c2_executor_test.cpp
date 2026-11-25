// SPDX-License-Identifier: EPL-1.0
// Member C — Stage C2: Persistent NativeExecutor, Static Partitioning,
// Multi-Batch Reuse, Boundary Conditions, and AoS/SoA View Coverage Tests.

#include "executor.hpp"
#include "fcn_test_fixture.hpp"

#include <atomic>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void require(bool cond, const std::string& msg) {
    if (!cond) {
        throw std::runtime_error("C2 test FAILED: " + msg);
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

    // 1. Multi-batch persistent reuse across diverse sizes (0, 1, tail, grain>N, large).
    const std::vector<std::size_t> batch_sequence = {
        0, 1, 2, 7, 24, 31, 32, 33, 63, 64, 65, 127, 128, 129, 255, 257, 1000, 0, 1, 513};
    const std::vector<std::size_t> grains = {1, 16, 64, 128, 512};
    const std::vector<std::size_t> workers_list = {1, 2, 4, 8};

    for (std::size_t workers : workers_list) {
        auto exec = make_persistent_executor(workers);
        std::size_t expected_batches = 0;
        std::uint64_t expected_rows = 0;

        for (std::size_t grain : grains) {
            for (std::size_t n : batch_sequence) {
                const auto aos_inputs = tile_inputs(base_rows, n);
                const auto soa_storage = pack_soa_test_double(aos_inputs);
                const InputView aos_view = AosInputView{aos_inputs.data(), aos_inputs.size()};
                const InputView soa_view = soa_storage.view();

                std::vector<OutputRow> serial_aos(n);
                std::vector<OutputRow> serial_soa(n);
                const auto s_aos = evaluate_serial(
                    aos_view, OutputView{serial_aos.data(), serial_aos.size()},
                    evaluate_range_test_double);
                const auto s_soa = evaluate_serial(
                    soa_view, OutputView{serial_soa.data(), serial_soa.size()},
                    evaluate_range_test_double);
                require(!s_aos.used_taskflow && !s_soa.used_taskflow, "serial used_taskflow");
                verify_bit_identical(serial_aos, serial_soa, "serial AoS vs SoA");

                // Parallel AoS through persistent executor
                std::vector<OutputRow> par_aos(n);
                std::vector<std::atomic<int>> visits_aos(n);
                for (std::size_t i = 0; i < n; ++i) {
                    visits_aos[i].store(0, std::memory_order_relaxed);
                }
                const auto p_aos = exec->run_ranges(
                    n, grain, Schedule::static_partition,
                    [&](std::size_t begin, std::size_t end) {
                        require(RowRange{begin, end}.valid_for(n) && begin < end, "range bounds");
                        for (std::size_t i = begin; i < end; ++i) {
                            visits_aos[i].fetch_add(1, std::memory_order_relaxed);
                        }
                        evaluate_range_test_double(
                            aos_view, OutputView{par_aos.data(), par_aos.size()}, begin, end);
                    });
                ++expected_batches;
                expected_rows += n;
                require(p_aos.actual_workers == workers, "actual_workers mismatch");
                require(p_aos.used_taskflow == (n > 0), "parallel AoS used_taskflow");
                if (n == 0) {
                    require(p_aos.task_count == 0, "0-row batch must dispatch 0 tasks");
                } else {
                    require(p_aos.task_count >= 1, "non-empty batch must dispatch >= 1 task");
                }
                for (std::size_t i = 0; i < n; ++i) {
                    require(visits_aos[i].load(std::memory_order_relaxed) == 1,
                            "AoS coverage mismatch");
                }
                verify_bit_identical(
                    serial_aos, par_aos,
                    "AoS w=" + std::to_string(workers) + " g=" + std::to_string(grain) +
                        " n=" + std::to_string(n));

                // Parallel SoA through the SAME persistent executor (verifies zero stale state)
                std::vector<OutputRow> par_soa(n);
                const auto p_soa = exec->evaluate_ranges(
                    soa_view, OutputView{par_soa.data(), par_soa.size()}, grain,
                    Schedule::static_partition, evaluate_range_test_double);
                ++expected_batches;
                expected_rows += n;
                require(p_soa.used_taskflow == (n > 0), "parallel SoA used_taskflow");
                verify_bit_identical(
                    serial_aos, par_soa,
                    "SoA w=" + std::to_string(workers) + " g=" + std::to_string(grain) +
                        " n=" + std::to_string(n));
            }
        }

        require(exec->batches_executed() == expected_batches, "cumulative batches mismatch");
        require(exec->total_rows_executed() == expected_rows, "cumulative rows mismatch");
        require(exec->total_tasks_executed() > 0, "cumulative tasks must be > 0");
    }

    // 2. View validation tests (null pointers on non-zero sizes, mismatched sizes, empty null ok).
    {
        NativeExecutor exec(2);

        // Empty views with nullptr are allowed by R4 contract.
        const InputView empty_aos = AosInputView{nullptr, 0};
        const OutputView empty_out{nullptr, 0};
        const auto s0 = evaluate_serial(empty_aos, empty_out, evaluate_range_test_double);
        const auto p0 = exec.evaluate_ranges(
            empty_aos, empty_out, 32, Schedule::static_partition, evaluate_range_test_double);
        require(s0.task_count == 0 && p0.task_count == 0, "empty null views must succeed");

        // Mismatched size rejected before dispatch.
        std::vector<InputRow> in(4);
        std::vector<OutputRow> out(3);
        bool caught_size = false;
        try {
            (void)exec.evaluate_ranges(
                AosInputView{in.data(), in.size()}, OutputView{out.data(), out.size()}, 2,
                Schedule::static_partition, evaluate_range_test_double);
        } catch (const std::invalid_argument&) {
            caught_size = true;
        }
        require(caught_size, "mismatched view size must throw");

        // Null pointer on non-empty AoS rejected.
        bool caught_null_aos = false;
        try {
            (void)exec.evaluate_ranges(
                AosInputView{nullptr, 3}, OutputView{out.data(), out.size()}, 2,
                Schedule::static_partition, evaluate_range_test_double);
        } catch (const std::invalid_argument&) {
            caught_null_aos = true;
        }
        require(caught_null_aos, "null AoS data for non-empty view must throw");

        // Null pointer on non-empty OutputView rejected.
        bool caught_null_out = false;
        try {
            (void)exec.evaluate_ranges(
                AosInputView{in.data(), in.size()}, OutputView{nullptr, in.size()}, 2,
                Schedule::static_partition, evaluate_range_test_double);
        } catch (const std::invalid_argument&) {
            caught_null_out = true;
        }
        require(caught_null_out, "null OutputView data for non-empty view must throw");

        // Null RangeTask rejected.
        bool caught_null_task = false;
        try {
            RangeTask empty_task;
            (void)exec.run_ranges(4, 2, Schedule::static_partition, empty_task);
        } catch (const std::invalid_argument&) {
            caught_null_task = true;
        }
        require(caught_null_task, "empty RangeTask must throw");
    }

    std::cout << "[C2] PASS: Persistent NativeExecutor multi-batch reuse (workers=1/2/4/8, "
                 "grains=1/16/64/128/512, AoS+SoA), boundaries, and view validation verified.\n";
    return 0;
}

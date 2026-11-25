// SPDX-License-Identifier: EPL-1.0
// Member C — Stage C1: Pinned Taskflow v3.11.0 API & Scheduling Semantics Smoke Probe

#include "executor.hpp"
#include "fcn_test_fixture.hpp"

#include <taskflow/taskflow.hpp>

#include <atomic>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void require(bool cond, const std::string& msg) {
    if (!cond) {
        throw std::runtime_error("C1 smoke FAILED: " + msg);
    }
}

void verify_bit_identical(const std::vector<coreorder::OutputRow>& a,
                          const std::vector<coreorder::OutputRow>& b,
                          const std::string& label) {
    require(a.size() == b.size(), label + ": size mismatch");
    if (!a.empty()) {
        require(std::memcmp(a.data(), b.data(), a.size() * sizeof(coreorder::OutputRow)) == 0,
                label + ": byte-level output divergence");
    }
}

}  // namespace

int main(int argc, char** argv) {
    using namespace coreorder;
    using namespace coreorder::runtime;
    using namespace coreorder::runtime::test_fixture;

    const std::string fixture_path =
        (argc > 1) ? std::string(argv[1]) : std::string(COREORDER_FIXTURE_PATH);

    std::cout << "[C1] Taskflow version: " << tf::version() << " (TF_VERSION=" << TF_VERSION
              << ")\n";
    std::cout << "[C1] Contract version: " << contract_version << "\n";
    require(std::string(tf::version()) == "3.11.0", "expected pinned Taskflow 3.11.0");

    const auto base_rows = load_public_fcn_fixture(fixture_path);
    std::cout << "[C1] Loaded " << base_rows.size() << " real PAMS FCN fixture rows from "
              << fixture_path << "\n";

    // 1. Verify test double matches exact hex expectations in public fixture.
    {
        std::vector<InputRow> inputs;
        inputs.reserve(base_rows.size());
        for (const auto& r : base_rows) {
            inputs.push_back(r.input);
        }
        std::vector<OutputRow> out(inputs.size());
        const InputView aos_view = AosInputView{inputs.data(), inputs.size()};
        const auto stats = evaluate_serial(
            aos_view, OutputView{out.data(), out.size()}, evaluate_range_test_double);
        require(!stats.used_taskflow && stats.task_count == 1, "serial stats mismatch");
        for (std::size_t i = 0; i < base_rows.size(); ++i) {
            require(out[i].side == base_rows[i].expected.side &&
                        out[i].error == base_rows[i].expected.error,
                    "fixture side/error mismatch at row " + std::to_string(i));
            require(std::memcmp(&out[i].price, &base_rows[i].expected.price, sizeof(double)) == 0,
                    "fixture exact IEEE-754 double mismatch at row " + std::to_string(i));
        }
        std::cout << "[C1] Verified 24/24 real PAMS fixture rows bit-for-bit against hex oracle.\n";
    }

    // 2. Run serial vs static workers=1/2/4 on empty, single, and non-divisible sizes
    //    checking byte-identical results and exact-once coverage.
    const std::vector<std::size_t> test_sizes = {0, 1, 24, 137, 513};
    const std::vector<std::size_t> worker_counts = {1, 2, 4};
    const std::size_t grain = 32;

    for (std::size_t n : test_sizes) {
        const auto inputs = tile_inputs(base_rows, n);
        const InputView aos_view = AosInputView{inputs.data(), inputs.size()};

        std::vector<OutputRow> serial_out(n);
        const auto serial_stats = evaluate_serial(
            aos_view, OutputView{serial_out.data(), serial_out.size()},
            evaluate_range_test_double);
        require(!serial_stats.used_taskflow, "run_serial must not use Taskflow");
        require(serial_stats.task_count == (n == 0 ? 0u : 1u), "serial task_count");

        for (std::size_t w : worker_counts) {
            NativeExecutor exec(w);
            require(exec.requested_workers() == w && exec.actual_workers() == w,
                    "executor worker count mismatch");

            std::vector<OutputRow> par_out(n);
            std::vector<std::atomic<int>> visits(n);
            for (std::size_t i = 0; i < n; ++i) {
                visits[i].store(0, std::memory_order_relaxed);
            }

            const auto par_stats = exec.run_ranges(
                n, grain, Schedule::static_partition,
                [&](std::size_t begin, std::size_t end) {
                    require(RowRange{begin, end}.valid_for(n) && begin < end, "invalid subrange");
                    for (std::size_t i = begin; i < end; ++i) {
                        visits[i].fetch_add(1, std::memory_order_relaxed);
                    }
                    evaluate_range_test_double(
                        aos_view, OutputView{par_out.data(), par_out.size()}, begin, end);
                });

            require(par_stats.used_taskflow == (n > 0), "used_taskflow flag mismatch");
            for (std::size_t i = 0; i < n; ++i) {
                require(visits[i].load(std::memory_order_relaxed) == 1,
                        "row coverage != 1 at index " + std::to_string(i));
            }
            verify_bit_identical(
                serial_out, par_out,
                "n=" + std::to_string(n) + ",w=" + std::to_string(w));
        }
    }

    // 3. Verify invalid workers / grain / schedule rejection before dispatching tasks.
    {
        bool caught_zero_workers = false;
        try {
            NativeExecutor bad(0);
        } catch (const std::invalid_argument&) {
            caught_zero_workers = true;
        }
        require(caught_zero_workers, "workers=0 must throw std::invalid_argument");

        NativeExecutor exec(2);
        bool caught_zero_grain = false;
        try {
            (void)exec.run_ranges(10, 0, Schedule::static_partition,
                                  [](std::size_t, std::size_t) {});
        } catch (const std::invalid_argument&) {
            caught_zero_grain = true;
        }
        require(caught_zero_grain, "grain=0 must throw std::invalid_argument");

        bool caught_bad_schedule = false;
        try {
            (void)exec.run_ranges(10, 4, static_cast<Schedule>(99),
                                  [](std::size_t, std::size_t) {});
        } catch (const std::invalid_argument&) {
            caught_bad_schedule = true;
        }
        require(caught_bad_schedule, "unknown schedule must throw std::invalid_argument");
    }

    std::cout << "[C1] PASS: Taskflow v3.11.0 API, real FCN fixture (serial/static1/2/4), "
                 "boundaries, coverage, and error rejection verified.\n";
    return 0;
}

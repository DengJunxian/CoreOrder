// SPDX-License-Identifier: EPL-1.0
// Member C — Standalone Module-Level Runtime Microbenchmark (C2/C3 Diagnostic).
//
// IMPORTANT: This measures ONLY the C++ Taskflow scheduling & test-double FCN
// numeric range loop on hot pre-packed buffers. It is a module-level diagnostic
// microbenchmark and MUST NOT be presented as formal end-to-end CoreOrder system
// performance (which requires frozen G3 protocol, Python RNG/packing, and PAMS
// matching).

#include "executor.hpp"
#include "fcn_test_fixture.hpp"

#include <algorithm>
#include <chrono>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;

struct BenchResult {
    std::string mode;
    std::string schedule;
    std::size_t workers = 1;
    std::size_t rows = 0;
    std::size_t grain = 0;
    std::size_t task_count = 0;
    int warmup_iters = 0;
    int timed_iters = 0;
    double median_us = 0.0;
    double mean_us = 0.0;
    double min_us = 0.0;
    double max_us = 0.0;
    double p25_us = 0.0;
    double p75_us = 0.0;
};

double percentile(std::vector<double> sorted, double p) {
    if (sorted.empty()) {
        return 0.0;
    }
    const double idx = p * static_cast<double>(sorted.size() - 1);
    const auto lo = static_cast<std::size_t>(idx);
    const std::size_t hi = (lo + 1 < sorted.size()) ? lo + 1 : lo;
    const double frac = idx - static_cast<double>(lo);
    return sorted[lo] * (1.0 - frac) + sorted[hi] * frac;
}

BenchResult summarize(const std::string& mode,
                      const std::string& schedule,
                      std::size_t workers,
                      std::size_t rows,
                      std::size_t grain,
                      std::size_t task_count,
                      int warmup_iters,
                      std::vector<double> samples_us) {
    std::sort(samples_us.begin(), samples_us.end());
    const double sum = std::accumulate(samples_us.begin(), samples_us.end(), 0.0);
    BenchResult r;
    r.mode = mode;
    r.schedule = schedule;
    r.workers = workers;
    r.rows = rows;
    r.grain = grain;
    r.task_count = task_count;
    r.warmup_iters = warmup_iters;
    r.timed_iters = static_cast<int>(samples_us.size());
    r.median_us = percentile(samples_us, 0.50);
    r.mean_us = sum / static_cast<double>(samples_us.size());
    r.min_us = samples_us.front();
    r.max_us = samples_us.back();
    r.p25_us = percentile(samples_us, 0.25);
    r.p75_us = percentile(samples_us, 0.75);
    return r;
}

}  // namespace

int main(int argc, char** argv) {
    using namespace coreorder;
    using namespace coreorder::runtime;
    using namespace coreorder::runtime::test_fixture;

    const std::string fixture_path =
        (argc > 1) ? std::string(argv[1]) : std::string(COREORDER_FIXTURE_PATH);
    const auto base_rows = load_public_fcn_fixture(fixture_path);

    const std::vector<std::size_t> row_sizes = {24, 128, 1024, 16384, 65536};
    const std::vector<std::size_t> worker_counts = {1, 2, 4, 8};
    const std::vector<std::size_t> grains = {32, 128, 512};
    const int warmup_iters = 5;
    const int timed_iters = 25;

    std::vector<BenchResult> results;

    for (std::size_t rows : row_sizes) {
        const auto aos_inputs = tile_inputs(base_rows, rows);
        const InputView view = AosInputView{aos_inputs.data(), aos_inputs.size()};
        std::vector<OutputRow> ref_out(rows);
        std::vector<OutputRow> out(rows);

        // 1. Direct native-serial (no Taskflow executor created)
        {
            RunStats last{};
            for (int i = 0; i < warmup_iters; ++i) {
                last = evaluate_serial(
                    view, OutputView{ref_out.data(), ref_out.size()}, evaluate_range_test_double);
            }
            std::vector<double> samples;
            samples.reserve(timed_iters);
            for (int i = 0; i < timed_iters; ++i) {
                const auto t0 = Clock::now();
                last = evaluate_serial(
                    view, OutputView{out.data(), out.size()}, evaluate_range_test_double);
                const auto t1 = Clock::now();
                samples.push_back(
                    std::chrono::duration<double, std::micro>(t1 - t0).count());
            }
            if (std::memcmp(ref_out.data(), out.data(), rows * sizeof(OutputRow)) != 0) {
                throw std::runtime_error("serial output changed across iterations");
            }
            results.push_back(summarize("native-serial", "none", 1, rows, rows, last.task_count,
                                        warmup_iters, std::move(samples)));
        }

        // 2. Persistent Taskflow static across workers=1/2/4/8 with grain=128
        for (std::size_t w : worker_counts) {
            NativeExecutor exec(w);
            const std::size_t grain = 128;
            RunStats last{};
            for (int i = 0; i < warmup_iters; ++i) {
                last = exec.evaluate_ranges(
                    view, OutputView{out.data(), out.size()}, grain, Schedule::static_partition,
                    evaluate_range_test_double);
            }
            std::vector<double> samples;
            samples.reserve(timed_iters);
            for (int i = 0; i < timed_iters; ++i) {
                const auto t0 = Clock::now();
                last = exec.evaluate_ranges(
                    view, OutputView{out.data(), out.size()}, grain, Schedule::static_partition,
                    evaluate_range_test_double);
                const auto t1 = Clock::now();
                samples.push_back(
                    std::chrono::duration<double, std::micro>(t1 - t0).count());
            }
            if (std::memcmp(ref_out.data(), out.data(), rows * sizeof(OutputRow)) != 0) {
                throw std::runtime_error("static parallel output diverged from serial");
            }
            results.push_back(summarize("native-parallel", "static", w, rows, grain,
                                        last.task_count, warmup_iters, std::move(samples)));
        }

        // 3. Grain & dynamic ablation at workers=4 for rows >= 1024
        if (rows >= 1024) {
            NativeExecutor exec(4);
            for (std::size_t grain : grains) {
                for (Schedule sched : {Schedule::static_partition, Schedule::dynamic_partition}) {
                    if (sched == Schedule::static_partition && grain == 128) {
                        continue;  // already recorded above
                    }
                    RunStats last{};
                    for (int i = 0; i < warmup_iters; ++i) {
                        last = exec.evaluate_ranges(
                            view, OutputView{out.data(), out.size()}, grain, sched,
                            evaluate_range_test_double);
                    }
                    std::vector<double> samples;
                    samples.reserve(timed_iters);
                    for (int i = 0; i < timed_iters; ++i) {
                        const auto t0 = Clock::now();
                        last = exec.evaluate_ranges(
                            view, OutputView{out.data(), out.size()}, grain, sched,
                            evaluate_range_test_double);
                        const auto t1 = Clock::now();
                        samples.push_back(
                            std::chrono::duration<double, std::micro>(t1 - t0).count());
                    }
                    if (std::memcmp(ref_out.data(), out.data(), rows * sizeof(OutputRow)) != 0) {
                        throw std::runtime_error("ablation parallel output diverged from serial");
                    }
                    results.push_back(summarize("native-parallel", std::string(to_string(sched)),
                                                4, rows, grain, last.task_count, warmup_iters,
                                                std::move(samples)));
                }
            }
        }
    }

    // Emit structured JSON to stdout.
    std::cout << std::fixed << std::setprecision(3);
    std::cout << "{\n";
    std::cout << "  \"scope\": \"module_microbenchmark_hot_aos_test_double_only\",\n";
    std::cout << "  \"formal_end_to_end\": false,\n";
    std::cout << "  \"contract_version\": \"" << contract_version << "\",\n";
    std::cout << "  \"hardware_concurrency\": " << std::thread::hardware_concurrency() << ",\n";
    std::cout << "  \"fixture_base_rows\": " << base_rows.size() << ",\n";
    std::cout << "  \"records\": [\n";
    for (std::size_t i = 0; i < results.size(); ++i) {
        const auto& r = results[i];
        std::cout << "    {\"mode\": \"" << r.mode << "\", \"schedule\": \"" << r.schedule
                  << "\", \"workers\": " << r.workers << ", \"rows\": " << r.rows
                  << ", \"grain\": " << r.grain << ", \"task_count\": " << r.task_count
                  << ", \"warmup_iters\": " << r.warmup_iters
                  << ", \"timed_iters\": " << r.timed_iters << ", \"median_us\": " << r.median_us
                  << ", \"mean_us\": " << r.mean_us << ", \"p25_us\": " << r.p25_us
                  << ", \"p75_us\": " << r.p75_us << ", \"min_us\": " << r.min_us
                  << ", \"max_us\": " << r.max_us << "}";
        std::cout << ((i + 1 < results.size()) ? ",\n" : "\n");
    }
    std::cout << "  ]\n";
    std::cout << "}\n";
    return 0;
}

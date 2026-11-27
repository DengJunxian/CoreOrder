// SPDX-License-Identifier: EPL-1.0
// CoreOrder Member C — Deterministic Taskflow Runtime (R4-v1)
// Inherits Taskflow v3.11.0 (MIT, SHA 816b4ad53b44196c88f409eb7b4a25a0e3bfdf42)
// and CoreOrder public ABI (include/coreorder/contracts.hpp, coreorder-r4-v1).
#pragma once

#include <coreorder/contracts.hpp>

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace tf {
class Executor;
}

namespace coreorder::runtime {

enum class Schedule : std::int32_t {
    static_partition = 0,
    dynamic_partition = 1,
};

[[nodiscard]] constexpr std::string_view to_string(Schedule schedule) noexcept {
    switch (schedule) {
        case Schedule::static_partition:
            return "static";
        case Schedule::dynamic_partition:
            return "dynamic";
    }
    return "unknown";
}

[[nodiscard]] Schedule parse_schedule(std::string_view name);

struct RunStats {
    std::size_t requested_workers = 1;
    std::size_t actual_workers = 1;
    std::size_t rows = 0;
    std::size_t grain = 0;
    Schedule schedule = Schedule::static_partition;
    std::size_t task_count = 0;
    bool used_taskflow = false;
};

struct ThreadEnvEntry {
    std::string name;
    std::string value;
    bool is_set = false;
    bool is_single_thread = false;
};

struct NestedThreadingReport {
    std::vector<ThreadEnvEntry> entries;
    bool has_oversubscription_risk = false;
};

// Inspects common BLAS/OpenMP thread-count environment variables to detect
// potential nested oversubscription when running Taskflow worker pools.
[[nodiscard]] NestedThreadingReport detect_nested_threading_env();

// Returns recommended environment variable overrides (value "1") to freeze
// peripheral numerical libraries to single-threaded mode during parallel runs.
[[nodiscard]] std::vector<std::pair<std::string, std::string>>
recommended_single_thread_blas_env();

// Returns the logical row count of an InputView.
[[nodiscard]] std::size_t input_view_size(const InputView& input) noexcept;

// Validates that InputView and OutputView have identical row counts and
// non-null data pointers whenever row count > 0. Throws std::invalid_argument
// before any worker task is submitted.
void validate_views(const InputView& input, OutputView output);

using RangeTask = std::function<void(std::size_t begin, std::size_t end)>;

// Direct serial execution path (`native-serial`).
// Never constructs a Taskflow executor; executes [0, rows) synchronously on the
// caller thread when rows > 0, and returns immediately when rows == 0.
RunStats run_serial(std::size_t rows, const RangeTask& task);

template <typename Kernel>
RunStats evaluate_serial(const InputView& input, OutputView output, Kernel&& kernel) {
    validate_views(input, output);
    const std::size_t rows = output.size;
    return run_serial(rows, [&](std::size_t begin, std::size_t end) {
        kernel(input, output, begin, end);
    });
}

// Persistent Taskflow-backed range executor created once per simulation run
// and joined/destroyed at run end.
//
// Determinism contract:
//   1. Caller holds read-only numeric input views and exclusive output buffer
//      alive for the entire duration of run_ranges().
//   2. Every index in [0, rows) is dispatched to task(begin, end) in disjoint
//      half-open intervals [begin, end) satisfying RowRange{begin, end}.valid_for(rows),
//      covering [0, rows) exactly once.
//   3. No shared mutable state or Python/GIL calls occur inside tasks.
//   4. All worker tasks are strictly joined before run_ranges() returns or
//      rethrows any exception. If multiple chunks throw, the exception from the
//      smallest `begin` index is deterministically rethrown after full join.
//   5. Concurrent re-entry on the same NativeExecutor instance is rejected with
//      std::runtime_error.
class NativeExecutor {
public:
    explicit NativeExecutor(std::size_t workers);
    ~NativeExecutor() noexcept;

    NativeExecutor(const NativeExecutor&) = delete;
    NativeExecutor& operator=(const NativeExecutor&) = delete;
    NativeExecutor(NativeExecutor&&) = delete;
    NativeExecutor& operator=(NativeExecutor&&) = delete;

    [[nodiscard]] std::size_t requested_workers() const noexcept { return requested_workers_; }
    [[nodiscard]] std::size_t actual_workers() const noexcept;
    [[nodiscard]] std::size_t batches_executed() const noexcept {
        return batches_executed_.load(std::memory_order_relaxed);
    }
    [[nodiscard]] std::uint64_t total_tasks_executed() const noexcept {
        return total_tasks_executed_.load(std::memory_order_relaxed);
    }
    [[nodiscard]] std::uint64_t total_rows_executed() const noexcept {
        return total_rows_executed_.load(std::memory_order_relaxed);
    }

    // Dispatches [0, rows) across persistent Taskflow workers using the chosen
    // partitioner (StaticPartitioner or DynamicPartitioner) and chunk grain.
    // Even with workers == 1, non-empty batches execute through Taskflow so
    // `native-parallel, workers=1` honestly quantifies scheduler overhead.
    RunStats run_ranges(
        std::size_t rows,
        std::size_t grain,
        Schedule schedule,
        const RangeTask& task);

    template <typename Kernel>
    RunStats evaluate_ranges(
        const InputView& input,
        OutputView output,
        std::size_t grain,
        Schedule schedule,
        Kernel&& kernel) {
        validate_views(input, output);
        const std::size_t rows = output.size;
        return run_ranges(rows, grain, schedule, [&](std::size_t begin, std::size_t end) {
            kernel(input, output, begin, end);
        });
    }

private:
    std::size_t requested_workers_;
    std::unique_ptr<tf::Executor> executor_;
    std::atomic<bool> in_flight_{false};
    std::atomic<std::size_t> batches_executed_{0};
    std::atomic<std::uint64_t> total_tasks_executed_{0};
    std::atomic<std::uint64_t> total_rows_executed_{0};
};

// Convenience factory returning a shared persistent executor, suitable for
// capturing inside Member B's `ExecutorFactory` / `RangeExecutor` adapter.
[[nodiscard]] std::shared_ptr<NativeExecutor> make_persistent_executor(std::size_t workers);

}  // namespace coreorder::runtime

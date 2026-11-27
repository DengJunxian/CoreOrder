// SPDX-License-Identifier: EPL-1.0
// CoreOrder Member C — Deterministic Taskflow Runtime Implementation (R4-v1)
// Uses Taskflow v3.11.0 (MIT, SHA 816b4ad53b44196c88f409eb7b4a25a0e3bfdf42)
// APIs: tf::Executor, tf::Taskflow, tf::IndexRange, for_each_by_index,
// tf::StaticPartitioner, tf::DynamicPartitioner.

#include "executor.hpp"

#include <taskflow/algorithm/for_each.hpp>
#include <taskflow/taskflow.hpp>

#include <array>
#include <cstdlib>
#include <exception>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>

static_assert(TF_VERSION == 301100, "CoreOrder runtime requires pinned Taskflow v3.11.0");

namespace coreorder::runtime {

namespace {

class InFlightGuard {
public:
    explicit InFlightGuard(std::atomic<bool>& flag) : flag_(flag) {
        if (flag_.exchange(true, std::memory_order_acq_rel)) {
            throw std::runtime_error(
                "NativeExecutor::run_ranges does not permit concurrent re-entry on the same instance");
        }
    }

    ~InFlightGuard() noexcept { flag_.store(false, std::memory_order_release); }

    InFlightGuard(const InFlightGuard&) = delete;
    InFlightGuard& operator=(const InFlightGuard&) = delete;

private:
    std::atomic<bool>& flag_;
};

void validate_soa_pointers(const SoaInputView& soa) {
    if (soa.size == 0) {
        return;
    }
    if (soa.p_now == nullptr || soa.p_fund == nullptr || soa.p_then == nullptr ||
        soa.w_f == nullptr || soa.w_c == nullptr || soa.w_n == nullptr ||
        soa.noise_scale == nullptr || soa.order_margin == nullptr ||
        soa.z_noise == nullptr || soa.z_margin == nullptr || soa.window == nullptr ||
        soa.effective_window == nullptr || soa.mean_reversion == nullptr ||
        soa.margin_type == nullptr || soa.chart_sign == nullptr) {
        throw std::invalid_argument("SoaInputView contains null column pointer for non-empty batch");
    }
}

void validate_aos_pointer(const AosInputView& aos) {
    if (aos.size > 0 && aos.data == nullptr) {
        throw std::invalid_argument("AosInputView data pointer is null for non-empty batch");
    }
}

}  // namespace

Schedule parse_schedule(std::string_view name) {
    if (name == "static") {
        return Schedule::static_partition;
    }
    if (name == "dynamic") {
        return Schedule::dynamic_partition;
    }
    throw std::invalid_argument("unknown schedule: " + std::string(name));
}

NestedThreadingReport detect_nested_threading_env() {
    static constexpr std::array<const char*, 6> kThreadEnvVars = {
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "BLIS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    };

    NestedThreadingReport report;
    report.entries.reserve(kThreadEnvVars.size());
    for (const char* name : kThreadEnvVars) {
        ThreadEnvEntry entry;
        entry.name = name;
        const char* raw = std::getenv(name);
        if (raw != nullptr && raw[0] != '\0') {
            entry.is_set = true;
            entry.value = raw;
            entry.is_single_thread = (entry.value == "1");
        } else {
            entry.is_set = false;
            entry.value = "";
            entry.is_single_thread = false;
        }
        if (!entry.is_single_thread) {
            report.has_oversubscription_risk = true;
        }
        report.entries.push_back(std::move(entry));
    }
    return report;
}

std::vector<std::pair<std::string, std::string>> recommended_single_thread_blas_env() {
    return {
        {"OMP_NUM_THREADS", "1"},
        {"OPENBLAS_NUM_THREADS", "1"},
        {"MKL_NUM_THREADS", "1"},
        {"BLIS_NUM_THREADS", "1"},
        {"VECLIB_MAXIMUM_THREADS", "1"},
        {"NUMEXPR_NUM_THREADS", "1"},
    };
}

std::size_t input_view_size(const InputView& input) noexcept {
    return std::visit([](const auto& view) noexcept { return view.size; }, input);
}

void validate_views(const InputView& input, OutputView output) {
    const std::size_t in_size = input_view_size(input);
    if (in_size != output.size) {
        throw std::invalid_argument(
            "InputView size (" + std::to_string(in_size) + ") does not match OutputView size (" +
            std::to_string(output.size) + ")");
    }
    if (output.size > 0 && output.data == nullptr) {
        throw std::invalid_argument("OutputView data pointer is null for non-empty batch");
    }
    std::visit(
        [](const auto& view) {
            using ViewT = std::decay_t<decltype(view)>;
            if constexpr (std::is_same_v<ViewT, AosInputView>) {
                validate_aos_pointer(view);
            } else {
                validate_soa_pointers(view);
            }
        },
        input);
}

RunStats run_serial(std::size_t rows, const RangeTask& task) {
    if (!task) {
        throw std::invalid_argument("run_serial requires a callable RangeTask");
    }
    RunStats stats;
    stats.requested_workers = 1;
    stats.actual_workers = 1;
    stats.rows = rows;
    stats.grain = rows;
    stats.schedule = Schedule::static_partition;
    stats.used_taskflow = false;
    if (rows == 0) {
        stats.task_count = 0;
        return stats;
    }
    task(0, rows);
    stats.task_count = 1;
    return stats;
}

NativeExecutor::NativeExecutor(std::size_t workers) : requested_workers_(workers) {
    if (workers == 0) {
        throw std::invalid_argument("NativeExecutor requires workers >= 1");
    }
    executor_ = std::make_unique<tf::Executor>(workers);
}

NativeExecutor::~NativeExecutor() noexcept {
    // tf::Executor::~Executor waits for all submitted taskflows and joins all workers.
    executor_.reset();
}

std::size_t NativeExecutor::actual_workers() const noexcept {
    return executor_ ? executor_->num_workers() : 0;
}

RunStats NativeExecutor::run_ranges(
    std::size_t rows,
    std::size_t grain,
    Schedule schedule,
    const RangeTask& task) {
    if (grain == 0) {
        throw std::invalid_argument("NativeExecutor::run_ranges requires grain >= 1");
    }
    if (schedule != Schedule::static_partition && schedule != Schedule::dynamic_partition) {
        throw std::invalid_argument("NativeExecutor::run_ranges received unknown Schedule");
    }
    if (!task) {
        throw std::invalid_argument("NativeExecutor::run_ranges requires a callable RangeTask");
    }

    InFlightGuard guard(in_flight_);

    RunStats stats;
    stats.requested_workers = requested_workers_;
    stats.actual_workers = actual_workers();
    stats.rows = rows;
    stats.grain = grain;
    stats.schedule = schedule;

    if (rows == 0) {
        stats.task_count = 0;
        stats.used_taskflow = false;
        batches_executed_.fetch_add(1, std::memory_order_relaxed);
        return stats;
    }

    std::atomic<std::size_t> chunk_count{0};
    std::mutex error_mutex;
    std::size_t earliest_error_begin = std::numeric_limits<std::size_t>::max();
    std::exception_ptr earliest_error = nullptr;

    auto dispatch_subrange = [&](tf::IndexRange<std::size_t> subrange) {
        const std::size_t begin = subrange.begin();
        const std::size_t end = subrange.end();
        if (!RowRange{begin, end}.valid_for(rows)) {
            std::lock_guard<std::mutex> lock(error_mutex);
            if (begin < earliest_error_begin) {
                earliest_error_begin = begin;
                earliest_error = std::make_exception_ptr(
                    std::logic_error("Taskflow partitioner produced out-of-bounds RowRange"));
            }
            return;
        }
        if (begin == end) {
            return;
        }
        chunk_count.fetch_add(1, std::memory_order_relaxed);
        try {
            task(begin, end);
        } catch (...) {
            std::lock_guard<std::mutex> lock(error_mutex);
            if (begin < earliest_error_begin) {
                earliest_error_begin = begin;
                earliest_error = std::current_exception();
            }
        }
    };

    tf::Taskflow flow;
    const tf::IndexRange<std::size_t> full_range(0, rows, 1);
    if (schedule == Schedule::static_partition) {
        flow.for_each_by_index(full_range, dispatch_subrange, tf::StaticPartitioner(grain));
    } else {
        flow.for_each_by_index(full_range, dispatch_subrange, tf::DynamicPartitioner(grain));
    }

    // Strict join barrier: all Taskflow tasks finish touching caller buffers
    // before this function returns or propagates any captured exception.
    executor_->run(flow).get();

    const std::size_t executed_tasks = chunk_count.load(std::memory_order_relaxed);
    stats.task_count = executed_tasks;
    stats.used_taskflow = true;

    batches_executed_.fetch_add(1, std::memory_order_relaxed);
    total_tasks_executed_.fetch_add(executed_tasks, std::memory_order_relaxed);
    total_rows_executed_.fetch_add(rows, std::memory_order_relaxed);

    if (earliest_error != nullptr) {
        std::rethrow_exception(earliest_error);
    }

    return stats;
}

std::shared_ptr<NativeExecutor> make_persistent_executor(std::size_t workers) {
    return std::make_shared<NativeExecutor>(workers);
}

}  // namespace coreorder::runtime

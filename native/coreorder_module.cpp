// SPDX-License-Identifier: EPL-1.0
#include "fcn_binding.hpp"
#include "executor.hpp"

#include <pybind11/pybind11.h>

#include <atomic>
#include <stdexcept>

namespace {

std::atomic<std::size_t> executor_creations{0};

coreorder::runtime::Schedule runtime_schedule(coreorder::binding::Schedule schedule) {
    using Binding = coreorder::binding::Schedule;
    using Runtime = coreorder::runtime::Schedule;
    switch (schedule) {
        case Binding::static_partition: return Runtime::static_partition;
        case Binding::dynamic_partition: return Runtime::dynamic_partition;
    }
    throw std::invalid_argument("unknown FCN schedule");
}

coreorder::binding::RangeExecutor make_executor(std::size_t workers) {
    auto executor = coreorder::runtime::make_persistent_executor(workers);
    ++executor_creations;
    return [executor](std::size_t rows, std::size_t grain, coreorder::binding::Schedule schedule,
                      const coreorder::binding::RangeTask& task) {
        executor->run_ranges(rows, grain, runtime_schedule(schedule), task);
    };
}

}  // namespace

PYBIND11_MODULE(_coreorder_fcn, module) {
    coreorder::binding::bind_fcn(module, &make_executor);
    module.def("executor_creations", [] { return executor_creations.load(); });
}

// SPDX-License-Identifier: EPL-1.0
#pragma once

#include <cstddef>
#include <functional>

namespace pybind11 {
class module_;
}

namespace coreorder::binding {

enum class Schedule { static_partition, dynamic_partition };
using RangeTask = std::function<void(std::size_t begin, std::size_t end)>;

// An executor owns its persistent runtime. It must finish all callbacks before
// it returns or throws, and assign disjoint ranges that cover [0, rows).
using RangeExecutor = std::function<void(std::size_t rows, std::size_t grain,
                                         Schedule schedule, const RangeTask& task)>;
using ExecutorFactory = std::function<RangeExecutor(std::size_t workers)>;

// A/C supply the native factory in the integrated extension. Serial builds
// need no executor; requesting parallel without one raises an explicit error.
void bind_fcn(pybind11::module_& module, ExecutorFactory factory = {});

}  // namespace coreorder::binding

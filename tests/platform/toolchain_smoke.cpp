#include <pybind11/pybind11.h>
#include <taskflow/taskflow.hpp>

namespace {

int run() {
    int first = 0;
    int second = 0;
    tf::Taskflow tasks;
    tasks.emplace([&first] { first = 19; });
    tasks.emplace([&second] { second = 23; });

    tf::Executor executor(2);
    executor.run(tasks).get();
    return first + second;
}

}  // namespace

PYBIND11_MODULE(_coreorder_toolchain_smoke, module) {
    module.def("run", &run, pybind11::call_guard<pybind11::gil_scoped_release>());
}

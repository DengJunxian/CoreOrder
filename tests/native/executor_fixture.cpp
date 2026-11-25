// SPDX-License-Identifier: EPL-1.0
// Test fixture only. No runtime code from this executable path ships as C's executor.
#include "fcn_binding.hpp"

#include <pybind11/pybind11.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <future>
#include <memory>
#include <stdexcept>
#include <thread>
#include <vector>

namespace py = pybind11;
using namespace coreorder::binding;

namespace {
struct Probe {
    std::atomic_size_t creations{0};
    std::atomic_bool pause{false};
    std::atomic_bool waiting{false};
};
}  // namespace

PYBIND11_MODULE(_coreorder_fcn_test, module) {
    auto probe = std::make_shared<Probe>();
    bind_fcn(module, [probe](std::size_t workers) -> RangeExecutor {
        ++probe->creations;
        return [workers, probe](std::size_t rows, std::size_t grain, Schedule schedule, const RangeTask& task) {
            if (probe->pause) {
                using namespace std::chrono_literals;
                const auto deadline = std::chrono::steady_clock::now() + 5s;
                probe->waiting = true;
                while (probe->pause && std::chrono::steady_clock::now() < deadline) {
                    std::this_thread::sleep_for(1ms);
                }
                probe->waiting = false;
                if (probe->pause) {
                    throw std::runtime_error("test executor was not resumed");
                }
            }
            const std::size_t chunks = 1 + (rows - 1) / grain;
            std::vector<std::future<void>> jobs;
            // The last short chunk is included. Reverse visit order for the second schedule value.
            for (std::size_t worker = 0; worker < std::min(chunks, workers); ++worker) {
                jobs.push_back(std::async(std::launch::async, [&, worker] {
                    for (std::size_t slot = worker; slot < chunks; slot += workers) {
                        const auto chunk = schedule == Schedule::static_partition ? slot : chunks - slot - 1;
                        const auto begin = chunk * grain;
                        task(begin, begin + std::min(grain, rows - begin));
                    }
                }));
            }
            for (auto& job : jobs) {
                job.get();
            }
        };
    });
    module.def("test_factory_creations", [probe] { return probe->creations.load(); });
    module.def("test_pause_executor", [probe](bool pause) { probe->pause = pause; });
    module.def("test_executor_waiting", [probe] { return probe->waiting.load(); });
}

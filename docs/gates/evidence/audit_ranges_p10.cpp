// SPDX-License-Identifier: EPL-1.0
#include "executor.hpp"
#include <coreorder/contracts.hpp>

#include <atomic>
#include <cassert>
#include <chrono>
#include <cstring>
#include <future>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <thread>
#include <vector>

using namespace coreorder;
using namespace coreorder::runtime;

int main() {
    constexpr std::size_t grain = 3;
    for (auto workers : {1u, 2u, 4u}) {
        NativeExecutor executor(workers);
        assert(executor.actual_workers() == workers);
        std::size_t batches = 0;
        for (auto schedule : {Schedule::static_partition, Schedule::dynamic_partition}) {
            for (auto rows : {0u, 1u, 2u, 3u, 4u, 5u, 9u, 17u, 511u}) {
                std::vector<InputRow> values(rows);
                for (unsigned i = 0; i < rows; ++i) {
                    values[i] = InputRow{100.0, 102.0, 99.0, 1.0, 2.0, 0.5, 0.001,
                                         0.02, (i % 3) * 0.1, 0.0, 7, 2, 3, 0, i % 2 ? 1 : -1};
                }
                InputView input = AosInputView{values.data(), rows};
                std::vector<OutputRow> serial(rows), parallel(rows);
                std::vector<std::atomic<unsigned>> visits(rows);
                for (auto& visit : visits) {
                    visit.store(0);
                }
                evaluate_range(input, {serial.data(), rows}, 0, rows);
                const auto stats = executor.run_ranges(rows, grain, schedule,
                    [&](std::size_t begin, std::size_t end) {
                        assert(begin < end && end <= rows);
                        for (auto i = begin; i < end; ++i) {
                            ++visits[i];
                        }
                        evaluate_range(input, {parallel.data(), rows}, begin, end);
                    });
                assert(stats.used_taskflow == (rows != 0));
                assert(stats.rows == rows);
                for (const auto& count : visits) {
                    assert(count.load() == 1);
                }
                if (rows) {
                    assert(std::memcmp(serial.data(), parallel.data(), rows * sizeof(OutputRow)) == 0);
                }
                ++batches;
            }
            std::vector<std::atomic<unsigned>> visits(17);
            for (auto& count : visits) {
                count.store(0);
            }
            bool reported_first = false;
            try {
                executor.run_ranges(visits.size(), grain, schedule,
                    [&](std::size_t begin, std::size_t end) {
                        for (auto i = begin; i < end; ++i) {
                            ++visits[i];
                        }
                        throw std::runtime_error(begin == 0 ? "range 0" : "later range");
                    });
            } catch (const std::runtime_error& error) {
                reported_first = std::string_view(error.what()) == "range 0";
            }
            assert(reported_first);
            for (const auto& count : visits) {
                assert(count.load() == 1);
            }
            ++batches;
        }
        std::promise<void> entered, release;
        auto entered_signal = entered.get_future();
        auto release_signal = release.get_future();
        std::thread controller([&] {
            executor.run_ranges(1, grain, Schedule::static_partition,
                [&](std::size_t, std::size_t) {
                    entered.set_value();
                    release_signal.get();
                });
        });
        bool reentry_rejected = false;
        if (entered_signal.wait_for(std::chrono::seconds(5)) == std::future_status::ready) {
            try {
                executor.run_ranges(1, grain, Schedule::static_partition, [](auto, auto) {});
            } catch (const std::runtime_error& error) {
                reentry_rejected = std::string_view(error.what()).find("concurrent re-entry") != std::string_view::npos;
            }
        }
        release.set_value();
        controller.join();
        assert(reentry_rejected);
        assert(executor.batches_executed() == batches + 1);
        std::cout << "PASS actual workers=" << workers << " batches=" << executor.batches_executed()
                  << " exact row ownership, strict barrier, smallest thrown range, re-entry\n";
    }
}

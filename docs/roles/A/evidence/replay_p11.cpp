// SPDX-License-Identifier: EPL-1.0
#include <coreorder/contracts.hpp>

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 4) {
        return 2;
    }
    using coreorder::InputRow;
    using coreorder::OutputRow;
    using clock = std::chrono::steady_clock;
    const auto bytes = std::filesystem::file_size(argv[1]);
    if (bytes == 0 || bytes % sizeof(InputRow) != 0) {
        throw std::runtime_error("invalid AoS capture size");
    }
    std::vector<InputRow> input(bytes / sizeof(InputRow));
    std::ifstream source(argv[1], std::ios::binary);
    source.read(reinterpret_cast<char*>(input.data()), bytes);
    if (!source) {
        throw std::runtime_error("incomplete capture");
    }
    const auto repeats = std::stoul(argv[2]);
    if (repeats == 0) {
        return 2;
    }
    std::vector<OutputRow> output(input.size());
    const coreorder::InputView in = coreorder::AosInputView{input.data(), input.size()};
    const coreorder::OutputView out{output.data(), output.size()};
    clock::duration elapsed{};
    for (unsigned long i = 0; i < repeats; ++i) {
        const auto start = clock::now();
        coreorder::evaluate_range(in, out, 0, input.size());
        elapsed += clock::now() - start;
        for (const auto& row : output) {
            if (row.error != 0) {
                throw std::runtime_error("numeric error in real captured row");
            }
        }
    }
    std::ofstream raw(argv[3], std::ios::binary);
    raw.write(reinterpret_cast<const char*>(output.data()), output.size() * sizeof(OutputRow));
    if (!raw) {
        throw std::runtime_error("could not write replay outputs");
    }
    std::cout << "{\"scope\":\"serial evaluate_range only on warm captured AoS\","
              << "\"rows\":" << input.size() << ",\"repeats\":" << repeats
              << ",\"kernel_s\":" << std::chrono::duration<double>(elapsed).count() << "}\n";
}

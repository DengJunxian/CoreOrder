// SPDX-License-Identifier: EPL-1.0
#include <coreorder/contracts.hpp>

#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

using namespace coreorder;

int main() {
    const InputRow buy{100, 110, 100, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 1};
    auto bad = buy;
    bad.z_noise = std::numeric_limits<double>::quiet_NaN();
    auto empty = buy;
    empty.window = empty.effective_window = 0;
    std::array<InputRow, 3> input{buy, bad, empty};
    std::array<OutputRow, 3> output{{{9, 9, 9}, {9, 9, 9}, {9, 9, 9}}};
    const InputView view = AosInputView{input.data(), input.size()};
    const OutputView result{output.data(), output.size()};
    evaluate_range(AosInputView{nullptr, 0}, {nullptr, 0}, 0, 0);
    evaluate_range(view, result, 1, 2);
    if (output[0].error != 9 || output[2].error != 9 ||
        output[1].error != static_cast<int>(RowError::nonfinite)) {
        throw std::runtime_error("range wrote outside its output slots or missed its row error");
    }
    evaluate_range(view, result, 0, 1);
    evaluate_range(view, result, 2, 3);
    if (output[0].side != 1 || output[0].error != 0 || output[0].price <= 100 ||
        output[2].side != 0 || output[2].error != 0 || output[2].price != 0 || std::signbit(output[2].price)) {
        throw std::runtime_error("buy or empty result is incorrect");
    }
    bool bad_range = false;
    try {
        evaluate_range(view, result, 2, 4);
    } catch (const std::invalid_argument&) {
        bad_range = true;
    }
    if (!bad_range) {
        throw std::runtime_error("out-of-bounds range was accepted");
    }
    std::cout << "C++ range: empty, single, subrange, untouched slots and error propagation PASS\n";
}

#include <coreorder/contracts.hpp>

#include <iostream>
#include <stdexcept>

static_assert(coreorder::RowRange{0, 0}.valid_for(0));
static_assert(coreorder::RowRange{1, 4}.valid_for(4));
static_assert(!coreorder::RowRange{3, 2}.valid_for(4));
static_assert(!coreorder::RowRange{0, 5}.valid_for(4));

int main() {
    coreorder::InputRow input{100.0};
    coreorder::InputView view = coreorder::AosInputView{&input, 1};
    auto aos = std::get<coreorder::AosInputView>(view);
    std::cout << "InputRow " << sizeof(coreorder::InputRow) << " bytes align "
              << alignof(coreorder::InputRow) << ", OutputRow " << sizeof(coreorder::OutputRow)
              << " bytes align " << alignof(coreorder::OutputRow) << '\n';
    if (aos.size != 1 || aos.data[0].p_now != 100.0) {
        throw std::runtime_error("public AoS view did not preserve the input row");
    }
}

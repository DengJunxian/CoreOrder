// Independent representation check for the proposed coreorder-r4-v1 ABI.
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <limits>
#include <type_traits>

struct InputRow {
    double p_now, p_fund, p_then, w_f, w_c, w_n;
    double noise_scale, order_margin, z_noise, z_margin;
    std::int64_t window, effective_window, mean_reversion;
    std::int32_t margin_type, chart_sign;
};

struct OutputRow {
    double price;
    std::int32_t side, error;
};

static_assert(sizeof(double) == 8 && std::numeric_limits<double>::is_iec559);
static_assert(std::is_standard_layout_v<InputRow> && std::is_trivially_copyable_v<InputRow>);
static_assert(std::is_standard_layout_v<OutputRow> && std::is_trivially_copyable_v<OutputRow>);

int main() {
    std::cout << sizeof(InputRow) << ' ' << alignof(InputRow) << '\n';
    std::cout << offsetof(InputRow, p_now) << ' ' << offsetof(InputRow, p_fund) << ' '
              << offsetof(InputRow, p_then) << ' ' << offsetof(InputRow, w_f) << ' '
              << offsetof(InputRow, w_c) << ' ' << offsetof(InputRow, w_n) << ' '
              << offsetof(InputRow, noise_scale) << ' ' << offsetof(InputRow, order_margin) << ' '
              << offsetof(InputRow, z_noise) << ' ' << offsetof(InputRow, z_margin) << ' '
              << offsetof(InputRow, window) << ' ' << offsetof(InputRow, effective_window) << ' '
              << offsetof(InputRow, mean_reversion) << ' ' << offsetof(InputRow, margin_type) << ' '
              << offsetof(InputRow, chart_sign) << '\n';
    std::cout << sizeof(OutputRow) << ' ' << alignof(OutputRow) << '\n';
    std::cout << offsetof(OutputRow, price) << ' ' << offsetof(OutputRow, side) << ' '
              << offsetof(OutputRow, error) << '\n';
}

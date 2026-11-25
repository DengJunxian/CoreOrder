// SPDX-License-Identifier: EPL-1.0
#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <string_view>
#include <type_traits>
#include <variant>

namespace coreorder {

inline constexpr std::string_view contract_version = "coreorder-r4-v1";

enum class MarginType : std::int32_t { fixed = 0, normal = 1 };
enum class Side : std::int32_t { sell = -1, none = 0, buy = 1 };
enum class RowError : std::int32_t { ok = 0, invalid_input = 1, unknown_margin = 2, nonfinite = 3 };

struct alignas(8) InputRow {
    double p_now;
    double p_fund;
    double p_then;
    double w_f;
    double w_c;
    double w_n;
    double noise_scale;
    double order_margin;
    double z_noise;
    double z_margin;
    std::int64_t window;
    std::int64_t effective_window;
    std::int64_t mean_reversion;
    std::int32_t margin_type;
    std::int32_t chart_sign;
};

struct alignas(8) OutputRow {
    double price;
    std::int32_t side;
    std::int32_t error;
};

static_assert(sizeof(double) == 8 && std::numeric_limits<double>::is_iec559);
static_assert(std::is_standard_layout_v<InputRow> && std::is_trivially_copyable_v<InputRow>);
static_assert(std::is_standard_layout_v<OutputRow> && std::is_trivially_copyable_v<OutputRow>);
static_assert(sizeof(InputRow) == 112 && alignof(InputRow) == 8);
static_assert(sizeof(OutputRow) == 16 && alignof(OutputRow) == 8);
static_assert(offsetof(InputRow, p_now) == 0);
static_assert(offsetof(InputRow, p_fund) == 8);
static_assert(offsetof(InputRow, p_then) == 16);
static_assert(offsetof(InputRow, w_f) == 24);
static_assert(offsetof(InputRow, w_c) == 32);
static_assert(offsetof(InputRow, w_n) == 40);
static_assert(offsetof(InputRow, noise_scale) == 48);
static_assert(offsetof(InputRow, order_margin) == 56);
static_assert(offsetof(InputRow, z_noise) == 64);
static_assert(offsetof(InputRow, z_margin) == 72);
static_assert(offsetof(InputRow, window) == 80);
static_assert(offsetof(InputRow, effective_window) == 88);
static_assert(offsetof(InputRow, mean_reversion) == 96);
static_assert(offsetof(InputRow, margin_type) == 104);
static_assert(offsetof(InputRow, chart_sign) == 108);
static_assert(offsetof(OutputRow, price) == 0);
static_assert(offsetof(OutputRow, side) == 8);
static_assert(offsetof(OutputRow, error) == 12);

struct AosInputView {
    const InputRow* data;
    std::size_t size;
};

struct SoaInputView {
    const double* p_now;
    const double* p_fund;
    const double* p_then;
    const double* w_f;
    const double* w_c;
    const double* w_n;
    const double* noise_scale;
    const double* order_margin;
    const double* z_noise;
    const double* z_margin;
    const std::int64_t* window;
    const std::int64_t* effective_window;
    const std::int64_t* mean_reversion;
    const std::int32_t* margin_type;
    const std::int32_t* chart_sign;
    std::size_t size;
};

using InputView = std::variant<AosInputView, SoaInputView>;

struct OutputView {
    OutputRow* data;
    std::size_t size;
};

struct RowRange {
    std::size_t begin;
    std::size_t end;

    [[nodiscard]] constexpr bool valid_for(std::size_t rows) const noexcept {
        return begin <= end && end <= rows;
    }
};

// B implements this declaration. A task owns only output slots [begin, end).
void evaluate_range(const InputView& input, OutputView output, std::size_t begin, std::size_t end);

}  // namespace coreorder

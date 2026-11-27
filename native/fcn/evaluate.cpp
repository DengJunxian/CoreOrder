// SPDX-License-Identifier: EPL-1.0
// FCN numerical expression adapted from PAMS, commit
// 6cd53810103780770c5b5d6ee0069ccab9f4b358, pams/agents/fcn_agent.py,
// FCNAgent.submit_orders_by_market. See the repository EPL-1.0 license.
#include <coreorder/contracts.hpp>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <stdexcept>

namespace coreorder {
namespace {

OutputRow error_row(RowError error) noexcept {
    return {0.0, static_cast<std::int32_t>(Side::none), static_cast<std::int32_t>(error)};
}

OutputRow evaluate(const InputRow& row) noexcept {
    const bool fixed = row.margin_type == static_cast<std::int32_t>(MarginType::fixed);
    if (!fixed && row.margin_type != static_cast<std::int32_t>(MarginType::normal)) {
        return error_row(RowError::unknown_margin);
    }

    const double values[] = {row.p_now, row.p_fund, row.p_then, row.w_f, row.w_c, row.w_n,
                             row.noise_scale, row.order_margin, row.z_noise, row.z_margin};
    for (const double value : values) {
        if (!std::isfinite(value)) {
            return error_row(RowError::nonfinite);
        }
    }
    if (row.p_now <= 0.0 || row.p_fund <= 0.0 || row.p_then <= 0.0 ||
        row.w_f < 0.0 || row.w_c < 0.0 || row.w_n < 0.0 ||
        row.window < 0 || row.effective_window < 0 || row.effective_window > row.window ||
        (row.chart_sign != -1 && row.chart_sign != 1) || row.order_margin < 0.0 ||
        (fixed && (row.order_margin > 1.0 || row.z_margin != 0.0 || std::signbit(row.z_margin)))) {
        return error_row(RowError::invalid_input);
    }

    const double weight = (row.w_f + row.w_c) + row.w_n;
    const double fundamental_ratio = row.p_fund / row.p_now;
    const double chart_ratio = row.p_now / row.p_then;
    if (!std::isfinite(weight) || !std::isfinite(fundamental_ratio) || !std::isfinite(chart_ratio)) {
        return error_row(RowError::nonfinite);
    }
    if (weight == 0.0 || fundamental_ratio == 0.0 || chart_ratio == 0.0) {
        return error_row(RowError::invalid_input);
    }

    // Keep the separate reciprocals and the addition order of PAMS.
    const double fundamental_scale = 1.0 / static_cast<double>(std::max<std::int64_t>(row.mean_reversion, 1));
    const double fundamental_return = fundamental_scale * std::log(fundamental_ratio);
    const double chart_scale = 1.0 / static_cast<double>(std::max<std::int64_t>(row.effective_window, 1));
    const double chart_return = chart_scale * std::log(chart_ratio);
    const double noise_return = row.noise_scale * row.z_noise;
    const double weighted_return = ((row.w_f * fundamental_return) +
                                    ((row.w_c * chart_return) * row.chart_sign)) +
                                   (row.w_n * noise_return);
    const double expected_return = (1.0 / weight) * weighted_return;
    const double exponent = expected_return * static_cast<double>(row.window);
    if (!std::isfinite(exponent)) {
        return error_row(RowError::nonfinite);
    }
    const double prediction = row.p_now * std::exp(exponent);
    if (!std::isfinite(prediction)) {
        return error_row(RowError::nonfinite);
    }

    const Side side = prediction > row.p_now ? Side::buy
                    : prediction < row.p_now ? Side::sell : Side::none;
    double price = 0.0;
    if (!fixed) {
        // PAMS validates the normal candidate even when the direction is empty.
        price = prediction + row.z_margin * row.order_margin;
    } else if (side == Side::buy) {
        price = prediction * (1.0 - row.order_margin);
    } else if (side == Side::sell) {
        price = prediction * (1.0 + row.order_margin);
    }
    if (!std::isfinite(price)) {
        return error_row(RowError::nonfinite);
    }
    if (price < 0.0) {
        return error_row(RowError::invalid_input);
    }
    return {side == Side::none ? 0.0 : price, static_cast<std::int32_t>(side),
            static_cast<std::int32_t>(RowError::ok)};
}

bool has_data(const AosInputView& view) noexcept {
    return view.data != nullptr;
}

bool has_data(const SoaInputView& view) noexcept {
    return view.p_now && view.p_fund && view.p_then && view.w_f && view.w_c && view.w_n &&
           view.noise_scale && view.order_margin && view.z_noise && view.z_margin &&
           view.window && view.effective_window && view.mean_reversion && view.margin_type &&
           view.chart_sign;
}

InputRow load_row(const AosInputView& view, std::size_t i) noexcept {
    // Structured NumPy storage is bytes, with no requirement for a live C++ InputRow.
    InputRow row;
    const auto* bytes = reinterpret_cast<const unsigned char*>(view.data);
    std::memcpy(&row, bytes + i * sizeof(row), sizeof(row));
    return row;
}

InputRow load_row(const SoaInputView& view, std::size_t i) noexcept {
    return {view.p_now[i], view.p_fund[i], view.p_then[i], view.w_f[i], view.w_c[i], view.w_n[i],
            view.noise_scale[i], view.order_margin[i], view.z_noise[i], view.z_margin[i],
            view.window[i], view.effective_window[i], view.mean_reversion[i], view.margin_type[i],
            view.chart_sign[i]};
}

}  // namespace

void evaluate_range(const InputView& input, OutputView output, std::size_t begin, std::size_t end) {
    std::visit([&](const auto& view) {
        if (output.size != view.size || !RowRange{begin, end}.valid_for(view.size)) {
            throw std::invalid_argument("range and output size must match the input view");
        }
        if (begin == end) {
            return;
        }
        if (!output.data || !has_data(view)) {
            throw std::invalid_argument("non-empty range requires valid input and output storage");
        }

        auto* bytes = reinterpret_cast<unsigned char*>(output.data);
        for (std::size_t i = begin; i < end; ++i) {
            const OutputRow result = evaluate(load_row(view, i));
            std::memcpy(bytes + i * sizeof(result), &result, sizeof(result));
        }
    }, input);
}

}  // namespace coreorder

// SPDX-License-Identifier: EPL-1.0
// Member C's test reader for the public PAMS FCN rows. Tests call the production numerical kernel.
#pragma once

#include <coreorder/contracts.hpp>

#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace coreorder::runtime::test_fixture {

struct FixtureRow {
    InputRow input{};
    OutputRow expected{};
    std::int64_t agent_id = 0;
    std::int64_t market_id = 0;
    std::int64_t call_index = 0;
};

struct SoaStorage {
    std::vector<double> p_now;
    std::vector<double> p_fund;
    std::vector<double> p_then;
    std::vector<double> w_f;
    std::vector<double> w_c;
    std::vector<double> w_n;
    std::vector<double> noise_scale;
    std::vector<double> order_margin;
    std::vector<double> z_noise;
    std::vector<double> z_margin;
    std::vector<std::int64_t> window;
    std::vector<std::int64_t> effective_window;
    std::vector<std::int64_t> mean_reversion;
    std::vector<std::int32_t> margin_type;
    std::vector<std::int32_t> chart_sign;

    [[nodiscard]] SoaInputView view() const noexcept {
        return SoaInputView{
            p_now.data(),
            p_fund.data(),
            p_then.data(),
            w_f.data(),
            w_c.data(),
            w_n.data(),
            noise_scale.data(),
            order_margin.data(),
            z_noise.data(),
            z_margin.data(),
            window.data(),
            effective_window.data(),
            mean_reversion.data(),
            margin_type.data(),
            chart_sign.data(),
            p_now.size(),
        };
    }
};

inline SoaStorage pack_soa(const std::vector<InputRow>& aos) {
    SoaStorage soa;
    const std::size_t n = aos.size();
    soa.p_now.resize(n);
    soa.p_fund.resize(n);
    soa.p_then.resize(n);
    soa.w_f.resize(n);
    soa.w_c.resize(n);
    soa.w_n.resize(n);
    soa.noise_scale.resize(n);
    soa.order_margin.resize(n);
    soa.z_noise.resize(n);
    soa.z_margin.resize(n);
    soa.window.resize(n);
    soa.effective_window.resize(n);
    soa.mean_reversion.resize(n);
    soa.margin_type.resize(n);
    soa.chart_sign.resize(n);
    for (std::size_t i = 0; i < n; ++i) {
        soa.p_now[i] = aos[i].p_now;
        soa.p_fund[i] = aos[i].p_fund;
        soa.p_then[i] = aos[i].p_then;
        soa.w_f[i] = aos[i].w_f;
        soa.w_c[i] = aos[i].w_c;
        soa.w_n[i] = aos[i].w_n;
        soa.noise_scale[i] = aos[i].noise_scale;
        soa.order_margin[i] = aos[i].order_margin;
        soa.z_noise[i] = aos[i].z_noise;
        soa.z_margin[i] = aos[i].z_margin;
        soa.window[i] = aos[i].window;
        soa.effective_window[i] = aos[i].effective_window;
        soa.mean_reversion[i] = aos[i].mean_reversion;
        soa.margin_type[i] = aos[i].margin_type;
        soa.chart_sign[i] = aos[i].chart_sign;
    }
    return soa;
}

namespace detail {

inline std::size_t find_key_value_start(const std::string& line, std::string_view key, std::size_t from = 0) {
    const std::string token = "\"" + std::string(key) + "\":";
    const std::size_t pos = line.find(token, from);
    if (pos == std::string::npos) {
        throw std::runtime_error("missing JSON key in fixture: " + std::string(key));
    }
    std::size_t val = pos + token.size();
    while (val < line.size() && (line[val] == ' ' || line[val] == '\t')) {
        ++val;
    }
    return val;
}

inline double parse_hex_double(const std::string& line, std::string_view key, std::size_t from = 0) {
    const std::size_t start = find_key_value_start(line, key, from);
    if (start >= line.size() || line[start] != '"') {
        throw std::runtime_error("expected quoted hex float for key: " + std::string(key));
    }
    const std::size_t end = line.find('"', start + 1);
    if (end == std::string::npos) {
        throw std::runtime_error("unterminated string for key: " + std::string(key));
    }
    const std::string text = line.substr(start + 1, end - start - 1);
    char* parse_end = nullptr;
    const double value = std::strtod(text.c_str(), &parse_end);
    if (parse_end == text.c_str() || *parse_end != '\0') {
        throw std::runtime_error("failed to parse hex double for key " + std::string(key) + ": " + text);
    }
    return value;
}

inline std::int64_t parse_int64(const std::string& line, std::string_view key, std::size_t from = 0) {
    const std::size_t start = find_key_value_start(line, key, from);
    char* parse_end = nullptr;
    const long long value = std::strtoll(line.c_str() + start, &parse_end, 10);
    if (parse_end == line.c_str() + start) {
        throw std::runtime_error("failed to parse int64 for key: " + std::string(key));
    }
    return static_cast<std::int64_t>(value);
}

}  // namespace detail

inline std::vector<FixtureRow> load_public_fcn_fixture(const std::string& path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("failed to open public FCN fixture: " + path);
    }
    std::vector<FixtureRow> rows;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty()) {
            continue;
        }
        const std::size_t input_pos = line.find("\"input\":");
        const std::size_t output_pos = line.find("\"output\":");
        if (input_pos == std::string::npos || output_pos == std::string::npos) {
            throw std::runtime_error("malformed FCN fixture line");
        }
        FixtureRow row;
        row.agent_id = detail::parse_int64(line, "agent_id");
        row.market_id = detail::parse_int64(line, "market_id");
        row.call_index = detail::parse_int64(line, "call_index");

        row.input.p_now = detail::parse_hex_double(line, "p_now", input_pos);
        row.input.p_fund = detail::parse_hex_double(line, "p_fund", input_pos);
        row.input.p_then = detail::parse_hex_double(line, "p_then", input_pos);
        row.input.w_f = detail::parse_hex_double(line, "w_f", input_pos);
        row.input.w_c = detail::parse_hex_double(line, "w_c", input_pos);
        row.input.w_n = detail::parse_hex_double(line, "w_n", input_pos);
        row.input.noise_scale = detail::parse_hex_double(line, "noise_scale", input_pos);
        row.input.order_margin = detail::parse_hex_double(line, "order_margin", input_pos);
        row.input.z_noise = detail::parse_hex_double(line, "z_noise", input_pos);
        row.input.z_margin = detail::parse_hex_double(line, "z_margin", input_pos);
        row.input.window = detail::parse_int64(line, "window", input_pos);
        row.input.effective_window = detail::parse_int64(line, "effective_window", input_pos);
        row.input.mean_reversion = detail::parse_int64(line, "mean_reversion", input_pos);
        row.input.margin_type =
            static_cast<std::int32_t>(detail::parse_int64(line, "margin_type", input_pos));
        row.input.chart_sign =
            static_cast<std::int32_t>(detail::parse_int64(line, "chart_sign", input_pos));

        row.expected.price = detail::parse_hex_double(line, "price", output_pos);
        row.expected.side =
            static_cast<std::int32_t>(detail::parse_int64(line, "side", output_pos));
        row.expected.error =
            static_cast<std::int32_t>(detail::parse_int64(line, "error", output_pos));
        rows.push_back(row);
    }
    if (rows.empty()) {
        throw std::runtime_error("public FCN fixture contained zero rows: " + path);
    }
    return rows;
}

inline std::vector<InputRow> tile_inputs(const std::vector<FixtureRow>& base, std::size_t count) {
    std::vector<InputRow> result(count);
    for (std::size_t i = 0; i < count; ++i) {
        result[i] = base[i % base.size()].input;
    }
    return result;
}

}  // namespace coreorder::runtime::test_fixture

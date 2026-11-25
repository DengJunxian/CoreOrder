// SPDX-License-Identifier: EPL-1.0
#include "../../native/layout/abi.hpp"
#include <fstream>
#include <iostream>
#include <string>

using coreorder::InputRow;
using coreorder::OutputRow;
using coreorder::layout::RowIdentity;

int main(int argc, char** argv) {
  if (argc == 2) {
    // Read NumPy's bytes into live C++ objects and check every field by name.
    std::ifstream stream(argv[1], std::ios::binary);
    for (int i = 0; i < 2; ++i) {
      InputRow r{};
      OutputRow o{};
      RowIdentity m{};
      stream.read(reinterpret_cast<char*>(&r), sizeof(r));
      stream.read(reinterpret_cast<char*>(&o), sizeof(o));
      stream.read(reinterpret_cast<char*>(&m), sizeof(m));
      if (!stream || r.p_now != i + 0.25 || r.p_fund != i + 1.25 ||
          r.p_then != i + 2.25 || r.w_f != i + 3.25 || r.w_c != i + 4.25 ||
          r.w_n != i + 5.25 || r.noise_scale != i + 6.25 || r.order_margin != i + 7.25 ||
          r.z_noise != i + 8.25 || r.z_margin != i + 9.25 || r.window != (1LL << 40) + i ||
          r.effective_window != i || r.mean_reversion != -2 - i ||
          r.margin_type != i || r.chart_sign != 1 - 2 * i ||
          o.price != i + 20.5 || o.side != 2 * i - 1 || o.error != i ||
          m.agent_id != 17 || m.market_id != 23 - i || m.call_index != 9) {
        std::cerr << "binary mismatch at row " << i << '\n';
        return 1;
      }
    }
    if (stream.peek() != std::char_traits<char>::eof()) return 1;
    std::cout << "PASS NumPy-to-C++ all fields, descending market IDs preserved\n";
    return 0;
  }
  // The Python ABI test reads these records and compares its dtype descriptors.
  std::cout << "input " << sizeof(InputRow) << ' ' << alignof(InputRow) << '\n';
  std::cout << "output " << sizeof(OutputRow) << ' ' << alignof(OutputRow) << '\n';
  std::cout << "metadata " << sizeof(RowIdentity) << ' ' << alignof(RowIdentity) << '\n';
#define PRINT_OFFSET(row, field) std::cout << #field << ' ' << offsetof(row, field) << '\n'
  PRINT_OFFSET(InputRow, p_now);
  PRINT_OFFSET(InputRow, p_fund);
  PRINT_OFFSET(InputRow, p_then);
  PRINT_OFFSET(InputRow, w_f);
  PRINT_OFFSET(InputRow, w_c);
  PRINT_OFFSET(InputRow, w_n);
  PRINT_OFFSET(InputRow, noise_scale);
  PRINT_OFFSET(InputRow, order_margin);
  PRINT_OFFSET(InputRow, z_noise);
  PRINT_OFFSET(InputRow, z_margin);
  PRINT_OFFSET(InputRow, window);
  PRINT_OFFSET(InputRow, effective_window);
  PRINT_OFFSET(InputRow, mean_reversion);
  PRINT_OFFSET(InputRow, margin_type);
  PRINT_OFFSET(InputRow, chart_sign);
  PRINT_OFFSET(OutputRow, price);
  PRINT_OFFSET(OutputRow, side);
  PRINT_OFFSET(OutputRow, error);
  PRINT_OFFSET(RowIdentity, agent_id);
  PRINT_OFFSET(RowIdentity, market_id);
  PRINT_OFFSET(RowIdentity, call_index);
#undef PRINT_OFFSET
}

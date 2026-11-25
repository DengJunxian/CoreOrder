// SPDX-License-Identifier: EPL-1.0
#pragma once

#include <coreorder/contracts.hpp>

namespace coreorder::layout {

static_assert(contract_version == "coreorder-r4-v1");

// D's sidecar accompanies both input views through Python order reconstruction.
// A call may have several accessible markets or no rows at all.
struct RowIdentity {
    std::int64_t agent_id;
    std::int64_t market_id;
    std::int64_t call_index;
};

static_assert(std::is_standard_layout_v<RowIdentity> && std::is_trivially_copyable_v<RowIdentity>);
static_assert(sizeof(RowIdentity) == 24 && alignof(RowIdentity) == 8);
static_assert(offsetof(RowIdentity, agent_id) == 0);
static_assert(offsetof(RowIdentity, market_id) == 8);
static_assert(offsetof(RowIdentity, call_index) == 16);

}  // namespace coreorder::layout

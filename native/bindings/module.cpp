// SPDX-License-Identifier: EPL-1.0
#include "fcn_binding.hpp"

#include <pybind11/pybind11.h>

PYBIND11_MODULE(_coreorder_fcn, module) {
    coreorder::binding::bind_fcn(module);
}

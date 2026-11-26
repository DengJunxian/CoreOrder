// SPDX-License-Identifier: EPL-1.0
#include "fcn_binding.hpp"

#include <coreorder/contracts.hpp>
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace coreorder::binding {
namespace {

class Evaluator {
public:
    Evaluator(Schedule schedule, std::size_t grain, RangeExecutor executor)
        : schedule_(schedule), grain_(grain), executor_(std::move(executor)) {}

    void run(const InputView& input, OutputView output) {
        if (!executor_) {
            evaluate_range(input, output, 0, output.size);
            return;
        }
        // A persistent executor may be in use on another Python thread.
        std::unique_lock<std::mutex> lock(mutex_, std::try_to_lock);
        if (!lock) {
            throw std::runtime_error("a parallel FCN evaluator is already running");
        }
        if (output.size != 0) {
            executor_(output.size, grain_, schedule_, [&](std::size_t begin, std::size_t end) {
                evaluate_range(input, output, begin, end);
            });
        }
    }

private:
    Schedule schedule_;
    std::size_t grain_;
    RangeExecutor executor_;
    std::mutex mutex_;
};

template <typename T>
py::array checked_array(py::handle object, const py::dtype& expected, const char* name) {
    const std::string label{name};
    if (!py::isinstance<py::array>(object)) {
        throw py::type_error(label + " must be a NumPy array");
    }
    auto array = py::reinterpret_borrow<py::array>(object);
    const auto dtype = array.dtype();
    if (!dtype.equal(expected) || !dtype.attr("isnative").cast<bool>() ||
        dtype.attr("alignment").cast<std::size_t>() != alignof(T)) {
        throw py::value_error(label + " has an invalid dtype, native byte order or dtype alignment");
    }
    if (array.ndim() != 1) {
        throw py::value_error(label + " must be one-dimensional");
    }
    const auto stride = array.strides(0);
    if (!(array.flags() & py::array::c_style) ||
        (stride != static_cast<py::ssize_t>(sizeof(T)) && !(array.size() == 0 && stride == 0))) {
        throw py::value_error(label + " must be C-contiguous with the ABI stride");
    }
    const auto address = reinterpret_cast<std::uintptr_t>(array.data());
    if (!(array.flags() & py::detail::npy_api::NPY_ARRAY_ALIGNED_) || address % alignof(T) != 0) {
        throw py::value_error(label + " buffer is not aligned");
    }
    return array;
}

template <typename T>
const T* soa_column(const py::dict& columns, const char* name, py::ssize_t& rows,
                    std::vector<py::array>& owners) {
    const auto key = py::str(name);
    if (!columns.contains(key)) {
        throw py::value_error(std::string("SoA is missing field ") + name);
    }
    auto array = checked_array<T>(columns[key], py::dtype::of<T>(), name);
    if (rows < 0) {
        rows = array.size();
    } else if (array.size() != rows) {
        throw py::value_error(std::string(name) + " length does not match other SoA fields");
    }
    const auto* data = static_cast<const T*>(array.data());
    owners.push_back(std::move(array));
    return data;
}

py::array run(Evaluator& evaluator, const InputView& input, const py::dtype& dtype, py::ssize_t rows) {
    auto output = checked_array<OutputRow>(py::array(dtype, rows), dtype, "output");
    auto* values = static_cast<OutputRow*>(output.mutable_data());
    const OutputView view{values, static_cast<std::size_t>(rows)};
    {
        py::gil_scoped_release release;
        evaluator.run(input, view);
    }
    for (py::ssize_t i = 0; i < rows; ++i) {
        std::int32_t error;
        const auto* bytes = reinterpret_cast<const unsigned char*>(values);
        std::memcpy(&error, bytes + i * sizeof(OutputRow) + offsetof(OutputRow, error), sizeof(error));
        if (error != static_cast<std::int32_t>(RowError::ok)) {
            throw py::value_error("FCN row " + std::to_string(i) + " failed with error " + std::to_string(error));
        }
    }
    return output;
}

}  // namespace

void bind_fcn(py::module_& module, ExecutorFactory factory) {
    PYBIND11_NUMPY_DTYPE(InputRow, p_now, p_fund, p_then, w_f, w_c, w_n, noise_scale,
                         order_margin, z_noise, z_margin, window, effective_window,
                         mean_reversion, margin_type, chart_sign);
    PYBIND11_NUMPY_DTYPE(OutputRow, price, side, error);
    const auto dtype = py::module_::import("numpy").attr("dtype");
    const auto input_dtype = dtype(py::dtype::of<InputRow>().attr("descr"), py::arg("align") = true).cast<py::dtype>();
    const auto output_dtype = dtype(py::dtype::of<OutputRow>().attr("descr"), py::arg("align") = true).cast<py::dtype>();

    module.attr("contract_version") = py::str(contract_version);
    py::class_<Evaluator>(module, "Evaluator")
        .def(py::init([factory = std::move(factory)](bool parallel, std::int64_t workers,
                                                    std::int64_t grain, const std::string& schedule) {
            if (workers <= 0 || grain <= 0 ||
                static_cast<std::uint64_t>(workers) > std::numeric_limits<std::size_t>::max() ||
                static_cast<std::uint64_t>(grain) > std::numeric_limits<std::size_t>::max()) {
                throw py::value_error("workers and grain must be positive size_t values");
            }
            if (schedule != "static" && schedule != "dynamic") {
                throw py::value_error("schedule must be static or dynamic");
            }
            RangeExecutor executor;
            if (parallel) {
                if (!factory || !(executor = factory(static_cast<std::size_t>(workers)))) {
                    throw std::runtime_error("native-parallel requires the production range executor");
                }
            } else if (workers != 1) {
                throw py::value_error("native-serial uses one worker");
            }
            const auto mode = schedule == "static" ? Schedule::static_partition : Schedule::dynamic_partition;
            return std::make_unique<Evaluator>(mode, static_cast<std::size_t>(grain), std::move(executor));
        }), py::kw_only(), py::arg("parallel") = false, py::arg("workers") = 1,
            py::arg("grain") = 128, py::arg("schedule") = "static")
        .def("aos", [input_dtype, output_dtype](Evaluator& evaluator, py::handle input) {
            const auto owner = checked_array<InputRow>(input, input_dtype, "AoS");
            return run(evaluator, AosInputView{static_cast<const InputRow*>(owner.data()),
                                                static_cast<std::size_t>(owner.size())}, output_dtype, owner.size());
        }, py::arg("input"))
        .def("soa", [output_dtype](Evaluator& evaluator, const py::dict& columns) {
            if (columns.size() != 15) {
                throw py::value_error("SoA must contain the 15 contract fields");
            }
            std::vector<py::array> owners;
            owners.reserve(15);
            py::ssize_t rows = -1;
            SoaInputView view{
                soa_column<double>(columns, "p_now", rows, owners),
                soa_column<double>(columns, "p_fund", rows, owners),
                soa_column<double>(columns, "p_then", rows, owners),
                soa_column<double>(columns, "w_f", rows, owners),
                soa_column<double>(columns, "w_c", rows, owners),
                soa_column<double>(columns, "w_n", rows, owners),
                soa_column<double>(columns, "noise_scale", rows, owners),
                soa_column<double>(columns, "order_margin", rows, owners),
                soa_column<double>(columns, "z_noise", rows, owners),
                soa_column<double>(columns, "z_margin", rows, owners),
                soa_column<std::int64_t>(columns, "window", rows, owners),
                soa_column<std::int64_t>(columns, "effective_window", rows, owners),
                soa_column<std::int64_t>(columns, "mean_reversion", rows, owners),
                soa_column<std::int32_t>(columns, "margin_type", rows, owners),
                soa_column<std::int32_t>(columns, "chart_sign", rows, owners),
                static_cast<std::size_t>(rows),
            };
            return run(evaluator, view, output_dtype, rows);
        }, py::arg("columns").noconvert());
}

}  // namespace coreorder::binding

"""CoreOrder R4 numeric buffers. Native consumers must join before lease exit."""

from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from math import isfinite
from numbers import Real
from operator import index
from threading import Lock, get_ident

import numpy as np


FLOAT_FIELDS = (
    "p_now", "p_fund", "p_then", "w_f", "w_c", "w_n",
    "noise_scale", "order_margin", "z_noise", "z_margin",
)
LONG_FIELDS = ("window", "effective_window", "mean_reversion")
INT_FIELDS = ("margin_type", "chart_sign")
INPUT_DTYPE = np.dtype(
    [(name, np.float64) for name in FLOAT_FIELDS]
    + [(name, np.int64) for name in LONG_FIELDS]
    + [(name, np.int32) for name in INT_FIELDS],
    align=True,
)
OUTPUT_DTYPE = np.dtype(
    [("price", np.float64), ("side", np.int32), ("error", np.int32)], align=True
)
METADATA_DTYPE = np.dtype(
    [(key, np.int64) for key in ("agent_id", "market_id", "call_index")], align=True
)


def _count(value):
    value = index(value)
    if value < 0:
        raise ValueError("row count must be nonnegative")
    return value


def _validate_array(arr, dtype, n):
    # NumPy considers singleton and empty arrays contiguous even with arbitrary
    # strides. Only a canonical tight stride (also zero for empty) is valid.
    if not isinstance(arr, np.ndarray):
        raise TypeError("expected ndarray; implicit conversion is disabled")
    if arr.dtype != dtype or arr.dtype.isalignedstruct != dtype.isalignedstruct:
        raise TypeError(f"expected native dtype {dtype}, got {arr.dtype}")
    if arr.shape != (n,) or not arr.flags.c_contiguous:
        raise ValueError("expected a C-contiguous vector of the exact row count")
    if arr.strides != (dtype.itemsize,) and not (n == 0 and arr.strides == (0,)):
        raise ValueError(f"noncanonical stride {arr.strides}")
    if not arr.flags.aligned or arr.ctypes.data % dtype.alignment:
        raise ValueError(f"buffer address must be aligned to {dtype.alignment}")


def validate_inputs(layout, inputs, n):
    """Check externally supplied buffers for B without copying or casting."""
    n = _count(n)
    if layout == "aos":
        _validate_array(inputs, INPUT_DTYPE, n)
    elif layout == "soa":
        if not isinstance(inputs, Mapping) or inputs.keys() != set(INPUT_DTYPE.names):
            raise ValueError("SoA requires exactly the R4 columns")
        for name in INPUT_DTYPE.names:
            _validate_array(inputs[name], INPUT_DTYPE[name], n)
    else:
        raise ValueError(f"unknown layout: {layout!r}")


def validate_output(output, n):
    """Check the writable B-owned result vector without creating a temporary."""
    _validate_array(output, OUTPUT_DTYPE, _count(n))
    if not output.flags.writeable:
        raise ValueError("output must be writable")


@dataclass(frozen=True)
class LayoutView:
    layout: str
    inputs: object
    metadata: np.ndarray
    stats: dict


def _integer(value, bits):
    if isinstance(value, (bool, np.bool_)):
        raise TypeError("boolean passed for integer field")
    value = index(value)
    limit = 1 << (bits - 1)
    if not -limit <= value < limit:
        raise OverflowError(f"value outside int{bits} range")
    return value


def _double(value):
    if not isinstance(value, Real):
        raise TypeError("expected a real scalar")
    value = float(value)
    if not isfinite(value):
        raise ValueError("non-finite numeric field")
    return value


class _Writer:
    def __init__(self, columns, metadata, n):
        self._columns = columns
        self._metadata = metadata
        self._n = n
        self._next = 0
        self._thread = get_ident()
        self._open = True

    def set_row(self, i, values, metadata):
        """Write one row in call/market order and reject narrowing integers."""
        if not self._open or get_ident() != self._thread:
            raise RuntimeError("writer is only valid on the filling thread during fill")
        if index(i) != self._next or i >= self._n:
            raise ValueError("write each row exactly once in increasing order")
        if len(values) != 15 or len(metadata) != 3:
            raise ValueError("expected 15 financial fields and 3 metadata fields")
        row = (tuple(map(_double, values[:10]))
               + tuple(_integer(x, 64) for x in values[10:13])
               + tuple(_integer(x, 32) for x in values[13:]))
        identity = tuple(_integer(x, 64) for x in metadata)
        if "rows" in self._columns:
            self._columns["rows"][i] = row
        else:
            for name, value in zip(INPUT_DTYPE.names, row):
                self._columns[name][i] = value
        self._metadata[i] = identity
        self._next += 1


class LayoutBuffer:
    """Reusable storage with exclusive fills and scoped, shared reads.

    A failed fill invalidates its partial batch. A later fill may reuse the
    capacity. A reader must finish using every borrowed array/pointer before
    its context exits. Attempting a fill during a lease fails immediately.
    """

    def __init__(self, layout):
        if layout not in ("aos", "soa"):
            raise ValueError(f"unknown layout: {layout!r}")
        self._layout = layout
        self._lock = Lock()
        self._writing = False
        self._readers = 0
        self._ready = False
        self._size = 0
        self._allocate(0)

    @property
    def layout(self):
        return self._layout

    def _allocate(self, capacity):
        if self.layout == "aos":
            columns = {"rows": np.empty(capacity, dtype=INPUT_DTYPE)}
        else:
            columns = {name: np.empty(capacity, dtype=INPUT_DTYPE[name])
                       for name in INPUT_DTYPE.names}
        metadata = np.empty(capacity, dtype=METADATA_DTYPE)
        self._columns = columns
        self._metadata = metadata
        self._capacity = capacity

    def _writeable(self, writeable):
        for array in self._columns.values():
            array.setflags(write=writeable)
        self._metadata.setflags(write=writeable)

    @contextmanager
    def _write(self, n):
        n = _count(n)
        with self._lock:
            if self._writing or self._readers:
                raise RuntimeError("layout buffer in use")
            self._writing = True
            self._ready = False
        try:
            if n > self._capacity:
                self._allocate(max(n, self._capacity * 2))
            self._writeable(True)
            writer = _Writer(self._columns, self._metadata, n)
            try:
                yield writer
            finally:
                writer._open = False
        finally:
            with self._lock:
                self._writing = False

    def _publish(self, writer):
        if writer._next != writer._n:
            raise ValueError(f"filled {writer._next} of {writer._n} rows")
        writer._open = False
        self._writeable(False)
        self._size = writer._n
        self._ready = True

    @contextmanager
    def fill(self, n):
        """Populate for a subsequent read, in a caller-serialized sequence."""
        with self._write(n) as writer:
            yield writer
            self._publish(writer)

    def _view(self):
        n = self._size
        if self.layout == "aos":
            inputs = self._columns["rows"][:n]
        else:
            # B's production binding accepts a py::dict. Each lease gets its
            # own field map; its borrowed ndarray values are read-only.
            inputs = {key: col[:n] for key, col in self._columns.items()}
        metadata = self._metadata[:n]
        reserved = {name: array.nbytes for name, array in self._columns.items()}
        active = {name: n * array.itemsize for name, array in self._columns.items()}
        stats = dict(n_rows=n, capacity=self._capacity, buffer_nbytes=active,
                     buffer_capacity_nbytes=reserved, input_nbytes=sum(active.values()),
                     metadata_nbytes=metadata.nbytes, metadata_capacity_nbytes=self._metadata.nbytes)
        return LayoutView(self.layout, inputs, metadata, stats)

    @contextmanager
    def read(self):
        with self._lock:
            if self._writing or not self._ready:
                raise RuntimeError("no completed batch available for reading")
            self._readers += 1
        try:
            yield self._view()
        finally:
            with self._lock:
                self._readers -= 1

    @contextmanager
    def packed(self, n, populate):
        """Atomically fill and lease precisely that batch, without a handoff gap."""
        with self._write(n) as writer:
            populate(writer)
            self._publish(writer)
            yield self._view()

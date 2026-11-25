"""D2 module harness. Run with PYTHONPATH=src and unittest discovery."""

import threading
import unittest

import numpy as np

from coreorder.packing import (
    INPUT_DTYPE, METADATA_DTYPE, OUTPUT_DTYPE, LayoutBuffer,
    validate_inputs, validate_output,
)


def fields(i):
    return tuple(i + j / 16 for j in range(10)) + (80 + i, i, 4, i % 2, 1 - 2 * (i % 2))


def identity(i):
    return (7 - i // 2, 2 - i % 2, i // 2)


def populate(writer, n):
    for i in range(n):
        writer.set_row(i, fields(i), identity(i))


class BufferTests(unittest.TestCase):
    def test_numpy_abi(self):
        self.assertEqual((112, 8), (INPUT_DTYPE.itemsize, INPUT_DTYPE.alignment))
        self.assertEqual([*range(0, 104, 8), 104, 108],
                         [INPUT_DTYPE.fields[f][1] for f in INPUT_DTYPE.names])
        self.assertEqual((16, 8), (OUTPUT_DTYPE.itemsize, OUTPUT_DTYPE.alignment))
        self.assertEqual([0, 8, 12], [OUTPUT_DTYPE.fields[f][1] for f in OUTPUT_DTYPE.names])
        self.assertEqual(24, METADATA_DTYPE.itemsize)

    def test_physical_buffers_roundtrip_and_accounting(self):
        snapshots = []
        for layout in ("aos", "soa"):
            storage = LayoutBuffer(layout)
            with storage.fill(7) as writer:
                populate(writer, 7)
            with storage.read() as view:
                self.assertEqual(layout, view.layout)
                validate_inputs(layout, view.inputs, 7)
                self.assertEqual([identity(i) for i in range(7)], view.metadata.tolist())
                self.assertEqual(7, view.stats["n_rows"])
                self.assertEqual(7 * 112, view.stats["input_nbytes"])
                self.assertEqual(7 * 24, view.stats["metadata_nbytes"])
                self.assertEqual(7 * 112, sum(view.stats["buffer_nbytes"].values()))
                self.assertEqual(7 * 112, sum(view.stats["buffer_capacity_nbytes"].values()))
                self.assertEqual(1 if layout == "aos" else 15, len(view.stats["buffer_nbytes"]))
                for j, key in enumerate(INPUT_DTYPE.names):
                    column = view.inputs[key]
                    self.assertEqual((112 if layout == "aos" else column.itemsize,), column.strides)
                    self.assertEqual([fields(i)[j] for i in range(7)], column.tolist())
                    self.assertFalse(column.flags.writeable)
                    with self.assertRaises(ValueError):
                        column.setflags(write=True)
                snapshots.append([view.inputs[key].tobytes() for key in INPUT_DTYPE.names])
                self.assertFalse(view.metadata.flags.writeable)
                if layout == "soa":
                    self.assertFalse(np.shares_memory(view.inputs["w_f"], view.inputs["w_c"]))
        self.assertEqual(*snapshots)

    def test_capacity_tail_and_empty(self):
        for layout in ("aos", "soa"):
            storage = LayoutBuffer(layout)
            for rows, capacity in [(0, 0), (3, 3), (4, 6), (1, 6), (0, 6)]:
                with storage.packed(rows, lambda writer: populate(writer, rows)) as view:
                    validate_inputs(layout, view.inputs, rows)
                    self.assertEqual(rows, len(view.metadata))
                    self.assertEqual(capacity, view.stats["capacity"])
                    self.assertEqual(capacity * 24, view.stats["metadata_capacity_nbytes"])
                    self.assertEqual(capacity * 112, sum(view.stats["buffer_capacity_nbytes"].values()))
                    if rows == 4:
                        previous = view.metadata.ctypes.data
                    if rows == 1:
                        self.assertEqual(previous, view.metadata.ctypes.data)

    def test_output_validation(self):
        results = np.empty(3, dtype=OUTPUT_DTYPE)
        validate_output(results, 3)
        validate_output(results[:0], 0)
        validate_output(results[-1:], 1)
        for broken in [results.reshape(1, 3), results[::-1], results["price"],
                       np.empty(3, dtype=OUTPUT_DTYPE.newbyteorder("S")),
                       np.ndarray((3,), OUTPUT_DTYPE, buffer=bytearray(49), offset=1)]:
            with self.assertRaises((TypeError, ValueError)):
                validate_output(broken, 3)
        results.setflags(write=False)
        with self.assertRaises(ValueError):
            validate_output(results, 3)

    def test_aos_shape_offset_stride_endian_and_alignment(self):
        arr = np.empty(6, dtype=INPUT_DTYPE)
        wrong_offsets = [INPUT_DTYPE.fields[key][1] for key in INPUT_DTYPE.names]
        wrong_offsets[:2] = wrong_offsets[1::-1]
        swapped = np.dtype(dict(names=INPUT_DTYPE.names, formats=[INPUT_DTYPE[k]
                           for k in INPUT_DTYPE.names], offsets=wrong_offsets, itemsize=112), align=True)
        for broken, n in [(arr[:2], 3), (arr.reshape(2, 3), 6), (arr[::2], 3),
                          (arr[::2][:1], 1), (arr[:1][::-1], 1), (arr.tolist(), 6),
                          (np.empty(1, swapped), 1), (np.empty(1, INPUT_DTYPE.newbyteorder("S")), 1),
                          (np.ndarray((3,), INPUT_DTYPE, buffer=bytearray(337), offset=1), 3)]:
            with self.assertRaises((TypeError, ValueError)):
                validate_inputs("aos", broken, n)

    def test_soa_rejects_malformed_columns(self):
        arr = {key: np.empty(3, dtype=INPUT_DTYPE[key]) for key in INPUT_DTYPE.names}
        validate_inputs("soa", arr, 3)
        for replacement in [np.zeros(3, "i4"), np.zeros(2), np.zeros(3).reshape(1, 3),
                            np.zeros(6)[::2], np.empty(3, np.dtype("f8").newbyteorder("S")),
                            np.ndarray((3,), "f8", bytearray(25), offset=1), [1., 2., 3.]]:
            with self.assertRaises((TypeError, ValueError)):
                validate_inputs("soa", dict(arr, p_now=replacement), 3)
        with self.assertRaises(ValueError):
            validate_inputs("soa", dict(arr, extra=1), 3)
        arr.pop("z_margin")
        with self.assertRaises(ValueError):
            validate_inputs("soa", arr, 3)

    def test_partial_failed_batch_never_read(self):
        for layout in ("aos", "soa"):
            storage = LayoutBuffer(layout)
            with storage.fill(1) as writer:
                populate(writer, 1)
            with self.assertRaises(ValueError):
                with storage.fill(2) as writer:
                    populate(writer, 1)
            with self.assertRaises(RuntimeError), storage.read():
                pass
            with self.assertRaises(RuntimeError):
                writer.set_row(1, fields(1), identity(1))
            with self.assertRaises(ArithmeticError):
                with storage.fill(1) as writer:
                    populate(writer, 1)
                    raise ArithmeticError("caller failed")
            with self.assertRaises(RuntimeError), storage.read():
                pass
            with storage.packed(1, lambda w: populate(w, 1)) as view:
                self.assertEqual(1, len(view.metadata))

    def test_invalid_scalar_and_index(self):
        for layout in ("aos", "soa"):
            buf = LayoutBuffer(layout)
            with self.assertRaises(ValueError), buf.fill(-1):
                pass
            for position, bad, exception in [(13, 2**31, OverflowError), (12, -(2**63)-1, OverflowError),
                                             (14, 1.2, TypeError), (0, float("nan"), ValueError)]:
                row = list(fields(0))
                row[position] = bad
                with self.assertRaises(exception), buf.fill(1) as writer:
                    writer.set_row(0, row, identity(0))
            with self.assertRaises(OverflowError), buf.fill(1) as writer:
                writer.set_row(0, fields(0), (0, 2**63, 0))
            with self.assertRaises(ValueError), buf.fill(2) as writer:
                writer.set_row(1, fields(0), identity(0))

    def test_lease_blocks_another_thread_until_exit(self):
        def attempt_fill():
            try:
                with storage.fill(77):
                    pass
            except RuntimeError:
                rejected.append(True)

        storage = LayoutBuffer("soa")
        rejected = []
        with storage.packed(2, lambda w: populate(w, 2)) as view:
            thread = threading.Thread(target=attempt_fill)
            thread.start()
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertEqual([True], rejected)
            self.assertEqual(2, len(view.metadata))
        with storage.read() as first, storage.read() as second:
            self.assertTrue(np.shares_memory(first.metadata, second.metadata))
            with self.assertRaises(RuntimeError), storage.fill(9):
                pass
        with storage.fill(3) as writer:
            populate(writer, 3)


if __name__ == "__main__":
    unittest.main()

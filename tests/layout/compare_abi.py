"""Compare the stdout of abi_check.cpp against NumPy's native aligned records."""

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np


def compare(executable):
    floats = "p_now p_fund p_then w_f w_c w_n noise_scale order_margin z_noise z_margin"
    ints = "window effective_window mean_reversion"
    dtypes = {
        "input": np.dtype(
            [(name, np.float64) for name in floats.split()]
            + [(name, np.int64) for name in ints.split()]
            + [(name, np.int32) for name in ("margin_type", "chart_sign")],
            align=True,
        ),
        "output": np.dtype(
            [("price", np.float64), ("side", np.int32), ("error", np.int32)], align=True
        ),
        "metadata": np.dtype(
            [(name, np.int64) for name in ("agent_id", "market_id", "call_index")],
            align=True,
        ),
    }
    expected = {}
    for key, dtype in dtypes.items():
        expected[key] = [dtype.itemsize, dtype.alignment]
        for name in dtype.names:
            expected[name] = [dtype.fields[name][1]]
    native = subprocess.check_output([executable], text=True)
    print(native, end="")
    actual = {}
    for line in native.splitlines():
        name, *values = line.split()
        actual[name] = list(map(int, values))
    if actual != expected:
        raise ValueError(f"C++ descriptors {actual} differ from NumPy {expected}")
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "rows.bin"
        with path.open("wb") as stream:
            for i in range(2):
                fields = tuple(i + j + 0.25 for j in range(10))
                fields += ((1 << 40) + i, i, -2 - i, i, 1 - 2 * i)
                for key, values in (("input", fields), ("output", (i + 20.5, 2 * i - 1, i)),
                                    ("metadata", (17, 23 - i, 9))):
                    row = np.array([values], dtype=dtypes[key])
                    stream.write(row.tobytes())
        subprocess.run([executable, str(path)], check=True)
    print(f"PASS numpy={np.__version__} python={sys.version.split()[0]} fields=21")


if __name__ == "__main__":
    compare(sys.argv[1])

"""Native-byte-order NumPy records for the CoreOrder R4-v1 layout."""

import numpy as np

CONTRACT_VERSION = "coreorder-r4-v1"

INPUT_DTYPE = np.dtype([
    ("p_now", np.float64),
    ("p_fund", np.float64),
    ("p_then", np.float64),
    ("w_f", np.float64),
    ("w_c", np.float64),
    ("w_n", np.float64),
    ("noise_scale", np.float64),
    ("order_margin", np.float64),
    ("z_noise", np.float64),
    ("z_margin", np.float64),
    ("window", np.int64),
    ("effective_window", np.int64),
    ("mean_reversion", np.int64),
    ("margin_type", np.int32),
    ("chart_sign", np.int32),
], align=True)
OUTPUT_DTYPE = np.dtype([
    ("price", np.float64),
    ("side", np.int32),
    ("error", np.int32),
], align=True)

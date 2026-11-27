import os
from pathlib import Path
import pytest

from validation.upstream import load


@pytest.fixture(scope="session")
def pams_root():
    root = Path(os.environ.get("COREORDER_PAMS_ROOT", "vendor/pams")).resolve()
    load(root)
    return root


@pytest.fixture(scope="session")
def small_config(pams_root):
    import json
    config = json.loads((pams_root / "samples/CI2002/config.json").read_text())
    config["FCNAgents"]["numAgents"] = 8
    config["FCNAgents"]["timeWindowSize"] = [2, 4]
    for s in config["simulation"]["sessions"]:
        s.update(iterationSteps=3, maxNormalOrders=3, withPrint=False)
    return config

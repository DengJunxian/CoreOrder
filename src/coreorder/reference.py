"""Independent invocation of the unchanged PAMS SequentialRunner.main entry point."""

import argparse
import random
from pathlib import Path

from pams.runners.sequential import SequentialRunner

from .run_records import run_recorded


def run_upstream(config_path, seed, observer):
    runner = SequentialRunner(settings=config_path, prng=random.Random(seed), logger=observer)
    observer.runner = runner
    runner.main()
    return runner, {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(
        backend="py-seq", book_restore="upstream", workers=1, layout=None, grain=None, schedule=None
    )
    return run_recorded(parser.parse_args(), run_upstream, entry_point="pams-reference")


if __name__ == "__main__":
    raise SystemExit(main())

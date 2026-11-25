"""Build and run B1's numerical and independent layout probes on Linux."""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FLAGS = ['-O3', '-std=c++17', '-fno-fast-math', '-ffp-contract=off']

INPUT_FIELDS = [
    ('p_now', 'f8'), ('p_fund', 'f8'), ('p_then', 'f8'), ('w_f', 'f8'),
    ('w_c', 'f8'), ('w_n', 'f8'), ('noise_scale', 'f8'), ('order_margin', 'f8'),
    ('z_noise', 'f8'), ('z_margin', 'f8'), ('window', 'i8'), ('effective_window', 'i8'),
    ('mean_reversion', 'i8'), ('margin_type', 'i4'), ('chart_sign', 'i4'),
]
OUTPUT_FIELDS = [('price', 'f8'), ('side', 'i4'), ('error', 'i4')]


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def check_abi(raw):
    rows = [list(map(int, line.split())) for line in raw.splitlines()]
    input_size, input_offsets, output_size, output_offsets = rows
    report = {}
    for name, fields, size, offsets, expected_size, expected_offsets in (
        ('input', INPUT_FIELDS, input_size, input_offsets, 112, [*range(0, 105, 8), 108]),
        ('output', OUTPUT_FIELDS, output_size, output_offsets, 16, [0, 8, 12]),
    ):
        dtype = np.dtype(fields, align=True)
        numpy_offsets = [dtype.fields[field][1] for field, _ in fields]
        buffer = np.zeros(2, dtype=dtype)
        report[name] = {
            'cpp_size_alignment': size,
            'numpy_size_alignment': [dtype.itemsize, dtype.alignment],
            'cpp_offsets': dict(zip(dtype.names, offsets, strict=True)),
            'numpy_offsets': dict(zip(dtype.names, numpy_offsets, strict=True)),
            'numpy_stride': buffer.strides[0],
            'numpy_address_aligned': bool(buffer.flags.aligned and buffer.ctypes.data % 8 == 0),
        }
        report[name]['match'] = (
            size == [dtype.itemsize, dtype.alignment] == [expected_size, 8]
            and offsets == numpy_offsets == expected_offsets
            and buffer.strides == (expected_size,)
            and report[name]['numpy_address_aligned']
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pams-source', type=Path, default=ROOT / 'vendor/pams')
    parser.add_argument('--pybind11', type=Path, default=ROOT / 'vendor/pybind11')
    parser.add_argument('--taskflow', type=Path, default=ROOT / 'vendor/taskflow')
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--output', type=Path, required=True, help='New directory for build and raw data')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True)
    evidence = {
        'platform': platform.platform(), 'python': sys.version,
        'source_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(HERE.iterdir()) if path.suffix in {'.py', '.cpp'}},
        'status': 'FAIL', 'commands': [],
    }

    def run(command, stdout_path=None):
        result = subprocess.run(command, text=True, encoding='utf-8', errors='replace', capture_output=True)
        record = {'command': command, 'exit_code': result.returncode, 'stderr': result.stderr}
        evidence['commands'].append(record)
        if stdout_path is None:
            record['stdout'] = result.stdout
        else:
            record['stdout_path'] = stdout_path.name
            stdout_path.write_text(result.stdout, encoding='utf-8')
        result.check_returncode()
        return result.stdout

    try:
        run([args.cxx, '--version'])
        run([sys.executable, '-m', 'pip', 'check'])
        run([sys.executable, '-m', 'pip', 'freeze', '--all'])
        extension = out / ('fcn_probe' + sysconfig.get_config_var('EXT_SUFFIX'))
        run([args.cxx, *FLAGS, '-shared', '-fPIC', '-pthread',
             '-I' + str(args.taskflow.resolve()), '-I' + str(args.pybind11.resolve() / 'include'),
             '-I' + sysconfig.get_paths()['include'], str(HERE / 'fcn_probe.cpp'), '-o', str(extension)])
        run([sys.executable, '-B', str(HERE / 'run_probe.py'), '--pams-source',
             str(args.pams_source.resolve()), '--native-module-dir', str(out)], out / 'probe.json')

        abi = out / 'abi_probe'
        run([args.cxx, *FLAGS, str(HERE / 'abi_probe.cpp'), '-o', str(abi)])
        abi_report = check_abi(run([str(abi)]))
        write_json(out / 'abi.json', abi_report)
        if not all(row['match'] for row in abi_report.values()):
            raise ValueError('C++ layout, NumPy layout and the proposed ABI differ')
        evidence['status'] = 'PASS'
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        evidence['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        write_json(out / 'run.json', evidence)
    print(f"{evidence['status']} {out / 'run.json'}")
    return int(evidence['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())

# Third-party sources and licenses

CoreOrder source uses the Eclipse Public License 1.0. Each Git submodule retains its upstream license, copyright notices, and source tree. The full commit IDs and license paths are recorded in [UPSTREAM.lock.json](UPSTREAM.lock.json).

| Component | Use in P01 | License |
| --- | --- | --- |
| PAMS 0.3.0 | Installed from the exact checkout in `vendor/pams` | [EPL-1.0](licenses/PAMS-EPL-1.0.txt) |
| Taskflow 3.11.0 | Headers used by the C++17 toolchain test | [MIT](licenses/Taskflow-MIT.txt) |
| pybind11 2.13.6 | Binding for the toolchain test | [BSD-3-Clause](licenses/pybind11-BSD-3-Clause.txt) |

PAMS reports version 0.3.0 at the locked commit. Its official 0.3.0 tag points to a different commit. Use the Git SHA in the lock when installing PAMS.

The development distributions in [requirements.lock](requirements.lock) are installed from their own wheels. Their distribution metadata and license files, including notices for bundled components, remain under each installed distribution's `.dist-info`. CoreOrder does not redistribute those wheels.

| Distribution | License recorded in the distribution |
| --- | --- |
| NumPy, SciPy | BSD-3-Clause, with notices for bundled code |
| tqdm | MPL-2.0 AND MIT |
| iniconfig, pip, pluggy, pytest | MIT |
| packaging | Apache-2.0 OR BSD-2-Clause |
| uv-build | MIT OR Apache-2.0 |
| CMake wheel and bundled CMake | Apache-2.0 for the wheel project and BSD-3-Clause for CMake, with notices for bundled code |
| colorama (Windows) | BSD-3-Clause |

Exact wheel versions and distribution names in the lock identify the releases on
[PyPI](https://pypi.org/). Consult the original license files before redistributing
any third-party package or binary.

The P02 serial and reference entry points invoke PAMS directly. The observer
reads its logger records and state without copying financial implementations.
The smoke workload derives from the EPL-1.0 PAMS
[samples/CI2002/config.json](https://github.com/masanorihirano/pams/blob/6cd53810103780770c5b5d6ee0069ccab9f4b358/samples/CI2002/config.json).
It changes the agent count and session lengths and sets the print flag and the
inherited order quota explicitly.

P03 uses the pinned JSON Schema validator in `requirements.lock`. jsonschema,
jsonschema-specifications, referencing, attrs and rpds-py use MIT licenses.
typing-extensions uses PSF-2.0. Consult the notices in the installed wheels.

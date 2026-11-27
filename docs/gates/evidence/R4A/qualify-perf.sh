#!/usr/bin/env bash
# Extract the official Ubuntu userspace frontend to the experiment folder only.
set -euo pipefail
root=$(realpath "$1")
tool_version=$2
cd "$root"
mkdir perf-tools
cd perf-tools
set -x
package=linux-tools-$tool_version
apt-cache show "$package" libpci3 libtraceevent1 | awk '/^(Package|Version|Filename|SHA256):/'
timeout --kill-after=3s 45s apt-get download "$package" libpci3 libtraceevent1
sha256sum ./*.deb
for deb in ./*.deb; do dpkg-deb --extract "$deb" extracted; done
export LD_LIBRARY_PATH="$PWD/extracted/usr/lib/x86_64-linux-gnu"
perf=$(find "$PWD/extracted" -type f -name perf -print -quit)
test -x "$perf"
ldd "$perf"
"$perf" version
mkdir bin
ln -s "$perf" bin/perf

cd "$root/source"
export PATH="$root/perf-tools/bin:$PWD/.venv/bin:$PATH" PYTHONPATH="$PWD:$PWD/build"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
for group in cpu branch l1 llc; do
    case $group in
        cpu) events=(--pmu-event cycles:u --pmu-event instructions:u) ;;
        branch) events=(--pmu-event branches:u --pmu-event branch-misses:u) ;;
        l1) events=(--pmu-event L1-dcache-loads:u --pmu-event L1-dcache-load-misses:u) ;;
        llc) events=(--pmu-event LLC-loads:u --pmu-event LLC-load-misses:u) ;;
    esac
    for workers in 1 4; do
        if (( workers == 1 )); then
            settings=(--backend native-serial)
        else
            settings=(--backend native-parallel --grain 128 --schedule static)
        fi
        # Unsupported groups still produce receipts. Their return codes remain visible.
        set +e
        taskset -c 0,2,4,6,8,10,12,14 python -m coreorder run --mode pmu --timeout 30 \
            --config configs/experiments/workloads/W2-H.json --seed 11 \
            --output "$root/pmu-core/$group-$workers" --book-restore incremental \
            --layout aos --workers "$workers" "${settings[@]}" "${events[@]}"
        printf '%s %s exit=%s\n' "$group" "$workers" "$?"
        set -e
    done
done

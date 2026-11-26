#!/usr/bin/env bash
# Read-only, unprivileged WSL inventory. Run before a serial benchmark session.
run() {
    printf '\n$'; printf ' %q' "$@"; printf '\n'
    "$@"
    printf 'exit=%s\n' "$?"
}
run date -u --iso-8601=seconds
run uname -srmo
run cat /etc/os-release
run lscpu
run lscpu -e=CPU,CORE,SOCKET,NODE,ONLINE,MHZ,MAXMHZ,MINMHZ
run lscpu -C
run taskset -pc $$
run taskset -c 0,2,4,6,8,10,12,14 python3 -c 'import os; print(sorted(os.sched_getaffinity(0)))'
run free -b
run df -B1 .
run gcc --version
run cat /proc/sys/kernel/perf_event_paranoid /proc/sys/kernel/nmi_watchdog
run ls -1 /sys/bus/event_source/devices/
run ls -1 /sys/bus/event_source/devices/cpu/{events,caps,format}
run sh -c 'head -35 /proc/cpuinfo; command -v perf; ls -d /usr/lib/linux-tools/*'
shopt -s nullglob
for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
    [[ -d "$cpu/cache" ]] || continue
    printf '\n%s ' "${cpu##*/}"
    for f in "$cpu"/topology/{core_id,thread_siblings_list,core_type} "$cpu"/cpufreq/{scaling_cur_freq,scaling_driver,scaling_governor}; do
        [[ -r "$f" ]] && printf '%s=%s ' "${f##*/}" "$(cat "$f")"
    done
    printf '\n'
    for index in "$cpu"/cache/index*; do
        printf '  %s ' "${index##*/}"
        for f in level type size shared_cpu_list coherency_line_size; do
            printf '%s=%s ' "$f" "$(cat "$index/$f")"
        done
        printf '\n'
    done
done
run ls -1 /sys/class/thermal /sys/devices/system/cpu/cpufreq
for f in /sys/class/hwmon/hwmon*/{name,temp*_input} /sys/class/power_supply/*/{type,online,status,capacity} /sys/class/thermal/thermal_zone*/{type,temp}; do
    [[ -r "$f" ]] && printf '%s=%s\n' "$f" "$(cat "$f")"
done
run cat /proc/loadavg
run uptime

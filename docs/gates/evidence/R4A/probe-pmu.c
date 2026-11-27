// Linux user-space PMU qualification on the current logical CPU mask.
#include <errno.h>
#include <inttypes.h>
#include <linux/perf_event.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>
#include <unistd.h>

#define CACHE(which, result) (PERF_COUNT_HW_CACHE_##which | (PERF_COUNT_HW_CACHE_RESULT_##result << 16))

static unsigned char working_set[32 * 1024 * 1024];
static volatile uint64_t checksum;

int main(void) {
    static const struct { const char *name; uint32_t type; uint64_t config; } events[] = {
        {"task-clock", PERF_TYPE_SOFTWARE, PERF_COUNT_SW_TASK_CLOCK},
        {"cycles", PERF_TYPE_HARDWARE, PERF_COUNT_HW_CPU_CYCLES},
        {"instructions", PERF_TYPE_HARDWARE, PERF_COUNT_HW_INSTRUCTIONS},
        {"branches", PERF_TYPE_HARDWARE, PERF_COUNT_HW_BRANCH_INSTRUCTIONS},
        {"branch-misses", PERF_TYPE_HARDWARE, PERF_COUNT_HW_BRANCH_MISSES},
        {"L1D-read-access", PERF_TYPE_HW_CACHE, CACHE(L1D, ACCESS)},
        {"L1D-read-miss", PERF_TYPE_HW_CACHE, CACHE(L1D, MISS)},
        {"LL-read-access", PERF_TYPE_HW_CACHE, CACHE(LL, ACCESS)},
        {"LL-read-miss", PERF_TYPE_HW_CACHE, CACHE(LL, MISS)},
        {"generic-cache-misses", PERF_TYPE_HARDWARE, PERF_COUNT_HW_CACHE_MISSES},
    };
    unsigned usable = 0;
    for (size_t i = 0; i < sizeof(events) / sizeof(events[0]); ++i) {
        struct perf_event_attr attr = {
            .size = sizeof(attr), .type = events[i].type, .config = events[i].config,
            .disabled = 1, .exclude_kernel = 1, .exclude_hv = 1,
            .read_format = PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING,
        };
        printf("%s type=%u config=%" PRIu64 " ", events[i].name, events[i].type, events[i].config);
        int fd = syscall(SYS_perf_event_open, &attr, 0, -1, -1, PERF_FLAG_FD_CLOEXEC);
        if (fd < 0) {
            int error = errno;
            printf("open_errno=%d (%s)\n", error, strerror(error));
            continue;
        }
        if (ioctl(fd, PERF_EVENT_IOC_ENABLE, 0) < 0) {
            perror("enable");
            close(fd);
            continue;
        }
        uint32_t generator = 1;
        uint64_t sum = 0;
        for (unsigned step = 0; step < 4000000; ++step) {
            generator = 1664525u * generator + 1013904223u;
            size_t index = (generator >> 7) & (sizeof(working_set) - 1);
            sum += ++working_set[index];
        }
        checksum = sum;
        if (ioctl(fd, PERF_EVENT_IOC_DISABLE, 0) < 0) {
            perror("disable");
            close(fd);
            continue;
        }
        uint64_t sample[3];
        ssize_t bytes = read(fd, sample, sizeof(sample));
        close(fd);
        if (bytes != sizeof(sample)) {
            printf("short_read=%zd\n", bytes);
            continue;
        }
        double coverage = sample[1] ? (double)sample[2] / sample[1] : 0;
        printf("value=%" PRIu64 " enabled_ns=%" PRIu64 " running_ns=%" PRIu64 " coverage=%.6f\n",
               sample[0], sample[1], sample[2], coverage);
        usable += i && sample[0] && coverage >= 0.95;
    }
    printf("scope=calling-thread user-space pid=0 cpu=-1 inherited=false checksum=%" PRIu64 "\n", checksum);
    return usable ? 0 : 2;
}

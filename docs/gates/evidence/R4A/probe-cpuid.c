// Build with cc on x86; pin each invocation to the logical CPU being queried.
#define _GNU_SOURCE
#include <cpuid.h>
#include <sched.h>
#include <stdio.h>

int main(void) {
    unsigned eax, ebx, ecx, edx;
    unsigned maximum = __get_cpuid_max(0x80000000u, NULL);
    printf("cpu=%d highest_extended=0x%08x\n", sched_getcpu(), maximum);
    if (maximum < 0x80000026u)
        return 0;
    for (unsigned level = 0; level < 8; ++level) {
        __cpuid_count(0x80000026u, level, eax, ebx, ecx, edx);
        printf("level=%u eax=%08x ebx=%08x ecx=%08x edx=%08x\n", level, eax, ebx, ecx, edx);
        if (!(ebx & 0xffff))
            break;
    }
    return 0;
}

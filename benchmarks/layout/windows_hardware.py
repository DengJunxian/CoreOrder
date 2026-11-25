"""Read-only Windows topology inventory for the D1 audit (single processor group)."""

import ctypes
import json
import platform
import winreg
from collections import Counter
from ctypes import wintypes


class Cache(ctypes.Structure):
    _fields_ = [
        ("level", ctypes.c_ubyte),
        ("associativity", ctypes.c_ubyte),
        ("line_bytes", wintypes.WORD),
        ("bytes", wintypes.DWORD),
        ("kind", ctypes.c_int),
    ]


class Details(ctypes.Union):
    _fields_ = [("cache", Cache), ("reserved", ctypes.c_uint64 * 2)]


class Processor(ctypes.Structure):
    _fields_ = [
        ("mask", ctypes.c_size_t),
        ("relationship", ctypes.c_int),
        ("details", Details),
    ]


class Memory(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
        (field, ctypes.c_uint64)
        for field in (
            "physical", "avail_physical", "pagefile", "avail_pagefile", "virtual",
            "avail_virtual", "avail_extended_virtual",
        )
    ]


def hardware():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    if kernel.GetActiveProcessorGroupCount() != 1:
        raise RuntimeError("This inventory requires one Windows processor group")
    extent = wintypes.DWORD()
    read = kernel.GetLogicalProcessorInformation
    read.argtypes = [ctypes.POINTER(Processor), ctypes.POINTER(wintypes.DWORD)]
    if read(None, ctypes.byref(extent)) or ctypes.get_last_error() != 122:
        raise ctypes.WinError(ctypes.get_last_error())
    records = (Processor * (extent.value // ctypes.sizeof(Processor)))()
    if not read(records, ctypes.byref(extent)):
        raise ctypes.WinError(ctypes.get_last_error())
    cores = [r.mask for r in records if r.relationship == 0]
    caches = Counter()
    kinds = ("unified", "instruction", "data", "trace")
    for record in records:
        if record.relationship == 2:
            cache = record.details.cache
            caches[(cache.level, kinds[cache.kind], cache.bytes, cache.line_bytes,
                    record.mask.bit_count())] += 1
    memory = Memory()
    memory.length = ctypes.sizeof(Memory)
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise ctypes.WinError(ctypes.get_last_error())
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as cpu:
        model, _ = winreg.QueryValueEx(cpu, "ProcessorNameString")
    return {
        "windows_version": platform.version(),
        "architecture": platform.machine(),
        "processor_name": model.strip(),
        "processor_groups": 1,
        "packages": sum(r.relationship == 3 for r in records),
        "physical_cores": len(cores),
        "logical_processors": sum(mask.bit_count() for mask in cores),
        "physical_ram_bytes": memory.physical,
        "caches": [
            dict(level=level, type=kind, bytes_each=size, line_bytes=line,
                 shared_by_logical_processors=sharing, instances=count)
            for (level, kind, size, line, sharing), count in sorted(caches.items())
        ],
    }


if __name__ == "__main__":
    print(json.dumps(hardware(), indent=2))

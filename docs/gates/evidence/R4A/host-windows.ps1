# Read-only host inventory invoked through WSL interop.
Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,CurrentClockSpeed,MaxClockSpeed,L2CacheSize,L3CacheSize | ConvertTo-Json -Compress
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,TotalVisibleMemorySize | ConvertTo-Json -Compress
Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,TotalPhysicalMemory | ConvertTo-Json -Compress
powercfg /GETACTIVESCHEME
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class CoreOrderCpuSets {
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool GetSystemCpuSetInformation(IntPtr p, uint len, out uint needed, IntPtr process, uint flags);
    public static void List() {
        uint size;
        GetSystemCpuSetInformation(IntPtr.Zero, 0, out size, IntPtr.Zero, 0);
        if (size == 0) throw new Win32Exception();
        IntPtr pointer = Marshal.AllocHGlobal((int)size);
        try {
            if (!GetSystemCpuSetInformation(pointer, size, out size, IntPtr.Zero, 0)) throw new Win32Exception();
            Console.WriteLine("group,logical_cpu,core,llc,numa,efficiency_class");
            for (int offset = 0; offset < size;) {
                IntPtr record = IntPtr.Add(pointer, offset);
                int length = Marshal.ReadInt32(record, 0);
                if (length < 8 || offset + length > size) throw new InvalidOperationException();
                if (Marshal.ReadInt32(record, 4) == 0 && length >= 20) {
                    Console.WriteLine("{0},{1},{2},{3},{4},{5}", Marshal.ReadInt16(record, 12),
                        Marshal.ReadByte(record, 14), Marshal.ReadByte(record, 15), Marshal.ReadByte(record, 16),
                        Marshal.ReadByte(record, 17), Marshal.ReadByte(record, 18));
                }
                offset += length;
            }
        } finally { Marshal.FreeHGlobal(pointer); }
    }
}
'@
[CoreOrderCpuSets]::List()
try { Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop | Select-Object CurrentTemperature,Active | ConvertTo-Json -Compress } catch { Write-Output ("MSAcpi_ThermalZoneTemperature: " + $_.Exception.Message) }
foreach ($class in @("Win32_PerfFormattedData_HvStats_HyperVHypervisorLogicalProcessor", "Win32_PerfFormattedData_Counters_ProcessorInformation", "Win32_PerfFormattedData_Counters_ThermalZoneInformation")) {
    Write-Output $class
    try {
        Get-CimInstance $class -ErrorAction Stop | Select-Object Name,Frequency,PercentTotalRunTime,ProcessorFrequency,PercentofMaximumFrequency,PercentProcessorPerformance,Temperature | ConvertTo-Json -Compress
    } catch { Write-Output $_.Exception.Message }
}

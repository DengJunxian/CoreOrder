# Observe the host during one diagnostic workload. Treat guest timing under observation as diagnostic.
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$ErrorActionPreference = "Stop"
$cpuClass = "Win32_PerfFormattedData_Counters_ProcessorInformation"
$hvClass = "Win32_PerfFormattedData_HvStats_HyperVHypervisorLogicalProcessor"
$thermalClass = "Win32_PerfFormattedData_Counters_ThermalZoneInformation"
function Sample ($name, $properties) {
    try {
        @(Get-CimInstance $name | Select-Object -Property $properties)
    } catch {
        @{ error = $_.Exception.Message }
    }
}
for ($i=0; $i -lt 12; $i++) {
    [ordered]@{
        utc = [DateTime]::UtcNow.ToString("o")
        logical_processors = Sample $cpuClass @("Name","PercentProcessorTime","ProcessorFrequency","PercentProcessorPerformance")
        hyper_v = Sample $hvClass @("Name","PercentTotalRunTime","Frequency")
        thermal_zones = Sample $thermalClass @("Name","Temperature","PercentPassiveLimit","ThrottleReasons")
    } | ConvertTo-Json -Depth 5 -Compress
    Start-Sleep -Milliseconds 800
}

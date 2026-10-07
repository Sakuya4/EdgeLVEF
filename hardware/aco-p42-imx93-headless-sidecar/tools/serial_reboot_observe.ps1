param(
    [string]$PortName = 'COM3',
    [Parameter(Mandatory=$true)][string]$EvidencePath,
    [int]$TimeoutSeconds = 180
)
$ErrorActionPreference = 'Stop'
$taskPort = [IO.Ports.SerialPort]::new($PortName,115200,'None',8,'One')
$taskPort.NewLine = "`n"
$taskPort.DtrEnable = $false
$taskPort.RtsEnable = $false
$taskPort.WriteTimeout = 3000
$taskTranscript = [Text.StringBuilder]::new()
try {
    $taskPort.Open()
    $taskPort.DiscardInBuffer()
    # Caller has an authenticated Linux shell; no keys are sent during autoboot.
    $taskPort.WriteLine('sync; reboot')
    $taskDeadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $taskDeadline) {
        if ($taskPort.BytesToRead -gt 0) {
            [void]$taskTranscript.Append($taskPort.ReadExisting())
            if ($taskTranscript.ToString() -match 'U-Boot SPL' -and $taskTranscript.ToString() -match '(?m)^.*imx93frdm login:') {
                Write-Output 'Unattended autoboot reached Linux login; no U-Boot commands or License submission sent.'
                exit 0
            }
        }
        Start-Sleep -Milliseconds 50
    }
    throw 'Unattended reboot did not reach the Linux login prompt; preserved boot evidence'
} finally {
    [IO.File]::WriteAllText([IO.Path]::GetFullPath($EvidencePath), $taskTranscript.ToString())
    if ($taskPort.IsOpen) { $taskPort.Close() }
    $taskPort.Dispose()
}

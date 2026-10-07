param(
    [string]$PortName = 'COM3',
    [Parameter(Mandatory=$true)][string]$EvidencePath
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
    # Caller must first confirm the authenticated Linux shell on COM3.
    $taskPort.WriteLine('sync; systemctl poweroff')
    $taskDeadline = [DateTime]::UtcNow.AddSeconds(45)
    while ([DateTime]::UtcNow -lt $taskDeadline) {
        if ($taskPort.BytesToRead -gt 0) {
            [void]$taskTranscript.Append($taskPort.ReadExisting())
            if ($taskTranscript.ToString() -match 'reboot: Power down') {
                Write-Output 'Confirmed Linux kernel Power down; ready for physical power removal.'
                exit 0
            }
        }
        Start-Sleep -Milliseconds 50
    }
    throw 'Power-down marker not observed; do not assume shutdown completed'
} finally {
    [IO.File]::WriteAllText([IO.Path]::GetFullPath($EvidencePath), $taskTranscript.ToString())
    if ($taskPort.IsOpen) { $taskPort.Close() }
    $taskPort.Dispose()
}

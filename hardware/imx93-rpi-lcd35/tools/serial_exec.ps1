param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [string]$PortName = "COM3",
    [int]$BaudRate = 115200,
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$serial = [System.IO.Ports.SerialPort]::new($PortName, $BaudRate, "None", 8, "One")
$serial.NewLine = "`n"
$serial.ReadTimeout = 250
$serial.WriteTimeout = 2000
$serial.DtrEnable = $false
$serial.RtsEnable = $false

function Read-Until([string]$Pattern, [int]$Milliseconds) {
    $deadline = [DateTime]::UtcNow.AddMilliseconds($Milliseconds)
    $text = [System.Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($serial.BytesToRead -gt 0) {
            [void]$text.Append($serial.ReadExisting())
            if ($text.ToString() -match $Pattern) {
                Start-Sleep -Milliseconds 150
                if ($serial.BytesToRead -gt 0) {
                    [void]$text.Append($serial.ReadExisting())
                }
                break
            }
        }
        Start-Sleep -Milliseconds 25
    }
    return $text.ToString()
}

try {
    $serial.Open()
    # Recover the console if a previous serial command was interrupted midway.
    $serial.Write(([string][char]3) + "`n")
    Start-Sleep -Milliseconds 250

    # A freshly booted board may still be at the getty prompt. Log in before
    # sending shell commands; otherwise the readiness probe becomes a username.
    $initial = Read-Until "login:|root@|# " 3000
    if ($initial -match "login:") {
        $serial.WriteLine("root")
        [void](Read-Until "root@|# " 3000)
    }

    $serial.WriteLine("echo __SERIAL_READY__")
    $ready = Read-Until "__SERIAL_READY__" 2500
    if ($ready -notmatch "__SERIAL_READY__") {
        $serial.WriteLine("root")
        [void](Read-Until "root@|#" 3000)
        $serial.WriteLine("echo __SERIAL_READY__")
        $ready = Read-Until "__SERIAL_READY__" 2500
    }

    $serial.WriteLine("$Command; serial_rc=`$?; echo __SERIAL_RC_`${serial_rc}__")
    $output = Read-Until "__SERIAL_RC_[0-9]+__" ($TimeoutSeconds * 1000)
    Write-Output $output
    if ($output -notmatch "__SERIAL_RC_([0-9]+)__") {
        throw "Timed out waiting for the target command to finish."
    }
    exit [int]$Matches[1]
}
finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
}

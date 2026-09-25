param(
    [string]$PortName = "COM3",
    [int]$BaudRate = 115200,
    [string]$SourceFile = "lcd35_spi_test.c",
    [string]$RemoteName = "lcd35_spi_test",
    [int]$RunTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$sourcePath = Join-Path $PSScriptRoot $SourceFile
$sourceBytes = [System.IO.File]::ReadAllBytes($sourcePath)
$encoded = [Convert]::ToBase64String($sourceBytes)
$remoteBase = "/tmp/$RemoteName"

$serial = [System.IO.Ports.SerialPort]::new($PortName, $BaudRate, "None", 8, "One")
$serial.NewLine = "`n"
$serial.ReadTimeout = 250
$serial.WriteTimeout = 2000
$serial.DtrEnable = $false
$serial.RtsEnable = $false

function Read-Available([int]$Milliseconds) {
    $deadline = [DateTime]::UtcNow.AddMilliseconds($Milliseconds)
    $text = [System.Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($serial.BytesToRead -gt 0) {
            [void]$text.Append($serial.ReadExisting())
            $deadline = [DateTime]::UtcNow.AddMilliseconds(250)
        }
        Start-Sleep -Milliseconds 25
    }
    return $text.ToString()
}

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
    $serial.Write("`n")
    Start-Sleep -Milliseconds 250
    $serial.DiscardInBuffer()

    $serial.WriteLine("echo __LCD35_CONSOLE_READY__")
    $ready = Read-Available 1200
    if ($ready -notmatch "__LCD35_CONSOLE_READY__") {
        $serial.WriteLine("root")
        [void](Read-Available 1000)
        $serial.WriteLine("echo __LCD35_CONSOLE_READY__")
        $ready = Read-Available 1200
    }
    if ($ready -notmatch "__LCD35_CONSOLE_READY__") {
        throw "COM3 did not reach a Linux shell. Received: $ready"
    }

    $serial.WriteLine("rm -f $remoteBase.c.b64 $remoteBase.c $remoteBase")
    [void](Read-Available 300)

    for ($offset = 0; $offset -lt $encoded.Length; $offset += 700) {
        $length = [Math]::Min(700, $encoded.Length - $offset)
        $chunk = $encoded.Substring($offset, $length)
        $serial.WriteLine("printf '%s' '$chunk' >> $remoteBase.c.b64")
        [void](Read-Available 80)
    }

    $serial.WriteLine("base64 -d $remoteBase.c.b64 > $remoteBase.c && gcc -O2 -Wall -Wextra -o $remoteBase $remoteBase.c && echo __LCD35_BUILD_OK__")
    $build = Read-Until "__LCD35_BUILD_OK__|error:" 15000
    Write-Output $build
    if ($build -notmatch "__LCD35_BUILD_OK__") {
        throw "Target build did not complete successfully."
    }

    $serial.WriteLine("$remoteBase; echo __LCD35_RUN_RC_`$?__")
    $run = Read-Until "__LCD35_RUN_RC_[0-9]+__" ($RunTimeoutSeconds * 1000)
    Write-Output $run
}
finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
}

param(
    [Parameter(Mandatory = $true)]
    [string]$LocalPath,
    [Parameter(Mandatory = $true)]
    [string]$RemotePath,
    [string]$PortName = "COM3",
    [int]$BaudRate = 115200,
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"

if ($RemotePath -notmatch '^/[A-Za-z0-9._/-]+$') {
    throw "RemotePath contains unsupported characters: $RemotePath"
}

$resolvedLocalPath = (Resolve-Path -LiteralPath $LocalPath).Path
$encoded = [Convert]::ToBase64String([IO.File]::ReadAllBytes($resolvedLocalPath))
$remoteEncodedPath = "$RemotePath.b64"

$serial = [IO.Ports.SerialPort]::new($PortName, $BaudRate, "None", 8, "One")
$serial.NewLine = "`n"
$serial.ReadTimeout = 250
$serial.WriteTimeout = 3000
$serial.DtrEnable = $false
$serial.RtsEnable = $false

function Read-Until([string]$Pattern, [int]$Milliseconds) {
    $deadline = [DateTime]::UtcNow.AddMilliseconds($Milliseconds)
    $text = [Text.StringBuilder]::new()
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($serial.BytesToRead -gt 0) {
            [void]$text.Append($serial.ReadExisting())
            if ($text.ToString() -match $Pattern) {
                Start-Sleep -Milliseconds 100
                if ($serial.BytesToRead -gt 0) {
                    [void]$text.Append($serial.ReadExisting())
                }
                break
            }
        }
        Start-Sleep -Milliseconds 20
    }
    return $text.ToString()
}

try {
    $serial.Open()
    $serial.Write(([string][char]3) + "`n")
    Start-Sleep -Milliseconds 250
    $serial.DiscardInBuffer()

    $serial.WriteLine("echo __SERIAL_UPLOAD_READY__")
    $readyPattern = '(?m)^__SERIAL_UPLOAD_READY__\r?$'
    $ready = Read-Until $readyPattern 2000
    if ($ready -notmatch $readyPattern) {
        throw "COM port did not reach a Linux shell."
    }

    $serial.WriteLine("rm -f $remoteEncodedPath $RemotePath")
    [void](Read-Until '[#\$] ' 500)

    for ($offset = 0; $offset -lt $encoded.Length; $offset += 700) {
        $length = [Math]::Min(700, $encoded.Length - $offset)
        $chunk = $encoded.Substring($offset, $length)
        $serial.WriteLine("printf '%s' '$chunk' >> $remoteEncodedPath")
        Start-Sleep -Milliseconds 35
    }

    $serial.WriteLine("base64 -d $remoteEncodedPath > $RemotePath && rm -f $remoteEncodedPath && echo __SERIAL_UPLOAD_OK__")
    $okPattern = '(?m)^__SERIAL_UPLOAD_OK__\r?$'
    $result = Read-Until $okPattern ($TimeoutSeconds * 1000)
    Write-Output $result
    if ($result -notmatch $okPattern) {
        throw "Upload did not complete successfully."
    }
}
finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
}

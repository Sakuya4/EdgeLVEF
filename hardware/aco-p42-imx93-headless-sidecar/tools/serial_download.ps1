param(
    [Parameter(Mandatory = $true)]
    [string]$RemotePath,
    [Parameter(Mandatory = $true)]
    [string]$LocalPath,
    [string]$PortName = "COM3",
    [int]$BaudRate = 115200,
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

if ($RemotePath -notmatch '^/[A-Za-z0-9._/-]+$') {
    throw "RemotePath contains unsupported characters: $RemotePath"
}

$resolvedLocalPath = [IO.Path]::GetFullPath($LocalPath)
$parent = [IO.Path]::GetDirectoryName($resolvedLocalPath)
if (-not [string]::IsNullOrWhiteSpace($parent)) {
    $null = New-Item -ItemType Directory -Path $parent -Force
}

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

    $initial = Read-Until "login:|root@|# " 3000
    if ($initial -match "login:") {
        $serial.WriteLine("root")
        [void](Read-Until "root@|# " 3000)
    }

    $serial.WriteLine("echo __SERIAL_DOWNLOAD_READY__")
    $readyPattern = '(?m)^__SERIAL_DOWNLOAD_READY__\r?$'
    $ready = Read-Until $readyPattern 2500
    if ($ready -notmatch $readyPattern) {
        throw "COM port did not reach a Linux shell."
    }

    $serial.DiscardInBuffer()
    $serial.WriteLine("stty -echo; printf '\n__SERIAL_DOWNLOAD_BEGIN__\n'; base64 -w0 $RemotePath; printf '\n__SERIAL_DOWNLOAD_END__\n'; stty echo")
    $result = Read-Until '(?m)^__SERIAL_DOWNLOAD_END__\r?$' ($TimeoutSeconds * 1000)

    $match = [regex]::Match(
        $result,
        '(?s)__SERIAL_DOWNLOAD_BEGIN__\r?\n(?<payload>[A-Za-z0-9+/=\r\n]+?)\r?\n__SERIAL_DOWNLOAD_END__'
    )
    if (-not $match.Success) {
        throw "Download did not complete successfully."
    }

    $encoded = $match.Groups['payload'].Value -replace '\s', ''
    $bytes = [Convert]::FromBase64String($encoded)
    [IO.File]::WriteAllBytes($resolvedLocalPath, $bytes)

    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedLocalPath).Hash
    Write-Output "Downloaded $RemotePath to $resolvedLocalPath"
    Write-Output "Bytes=$($bytes.Length) SHA256=$hash"
}
finally {
    if ($serial.IsOpen) {
        $serial.WriteLine("stty echo")
        $serial.Close()
    }
    $serial.Dispose()
}

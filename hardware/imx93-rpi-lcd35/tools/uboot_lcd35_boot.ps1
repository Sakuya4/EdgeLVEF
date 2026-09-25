param(
    [string]$PortName = "COM3",
    [int]$BaudRate = 115200,
    [string]$Image = "Image.lcd35",
    [string]$FdtFile = "imx93-11x11-frdm-lcd35.dtb",
    [switch]$SaveEnvironment,
    [int]$BootTimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$serial = [System.IO.Ports.SerialPort]::new($PortName, $BaudRate, "None", 8, "One")
$serial.NewLine = "`n"
$serial.ReadTimeout = 100
$serial.WriteTimeout = 2000
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$ubootPrompt = '(?m)^(?:u-boot)?=>\s*$'
$linuxPrompt = '(?m)^(?:[^\r\n]* login:|root@[^\r\n]*#)\s*$'

function Read-Until([string]$Pattern, [int]$TimeoutMilliseconds, [switch]$TapSpace) {
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    $buffer = [System.Text.StringBuilder]::new()
    $nextTap = [DateTime]::UtcNow

    while ([DateTime]::UtcNow -lt $deadline) {
        if ($serial.BytesToRead -gt 0) {
            $chunk = $serial.ReadExisting()
            [void]$buffer.Append($chunk)
            Write-Host -NoNewline $chunk
            if ($buffer.ToString() -match $Pattern) {
                return $buffer.ToString()
            }
        }

        if ($TapSpace -and [DateTime]::UtcNow -ge $nextTap) {
            $serial.Write(" ")
            $nextTap = [DateTime]::UtcNow.AddMilliseconds(100)
        }
        Start-Sleep -Milliseconds 20
    }

    throw "Timed out waiting for serial pattern: $Pattern"
}

function Invoke-UBootCommand([string]$Command) {
    $serial.WriteLine($Command)
    return Read-Until $ubootPrompt 10000
}

try {
    $serial.Open()
    $serial.DiscardInBuffer()
    $serial.Write(([string][char]3) + "`n")
    Start-Sleep -Milliseconds 250

    $initial = Read-Until "login:|root@|# |$ubootPrompt" 3000
    if ($initial -match "login:") {
        $serial.WriteLine("root")
        [void](Read-Until "root@|# " 3000)
    }

    if ($initial -notmatch $ubootPrompt) {
        $serial.WriteLine("reboot")
        # Tap space while U-Boot starts so even a zero-second autoboot delay is
        # interrupted. Stop only when the U-Boot command prompt is visible.
        [void](Read-Until $ubootPrompt 45000 -TapSpace)
    }

    [void](Invoke-UBootCommand "setenv image $Image")
    [void](Invoke-UBootCommand "setenv fdtfile $FdtFile")
    [void](Invoke-UBootCommand "printenv image fdtfile")

    if ($SaveEnvironment) {
        [void](Invoke-UBootCommand "saveenv")
    }

    $serial.WriteLine("boot")
    [void](Read-Until $linuxPrompt ($BootTimeoutSeconds * 1000))
    Write-Host "`nLCD35 boot reached the Linux console."
}
finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
    $serial.Dispose()
}

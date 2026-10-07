param(
    [Parameter(Mandatory = $true)][string]$LocalPath,
    [Parameter(Mandatory = $true)][string]$RemotePath,
    [string]$PortName = 'COM3',
    [ValidateSet(115200,230400,460800,921600)][int]$TransferBaudRate = 460800
)
$ErrorActionPreference = 'Stop'
if ($RemotePath -notmatch '^/opt/aco-sidecar/[A-Za-z0-9._/-]+$') { throw 'Invalid deployment path' }
$taskBytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $LocalPath).Path)
$taskHash = (Get-FileHash -LiteralPath $LocalPath -Algorithm SHA256).Hash.ToLowerInvariant()
$taskSerial = [IO.Ports.SerialPort]::new($PortName, 115200, 'None', 8, 'One')
$taskSerial.NewLine = "`n"
$taskSerial.ReadTimeout = 30000
$taskSerial.WriteTimeout = 10000
$taskSerial.DtrEnable = $false
$taskSerial.RtsEnable = $false
if (-not ('AcoSerialCrc32' -as [type])) {
    Add-Type -TypeDefinition @'
public static class AcoSerialCrc32 {
    private static readonly uint[] Table = MakeTable();
    private static uint[] MakeTable() {
        var table = new uint[256];
        for (uint i = 0; i < 256; i++) {
            uint crc = i;
            for (int bit = 0; bit < 8; bit++)
                crc = (crc & 1) != 0 ? (crc >> 1) ^ 0xedb88320u : crc >> 1;
            table[i] = crc;
        }
        return table;
    }
    public static uint Compute(byte[] bytes, int offset, int length) {
        uint crc = 0xffffffffu;
        for (int i = offset; i < offset + length; i++)
            crc = (crc >> 8) ^ Table[(crc ^ bytes[i]) & 255];
        return crc ^ 0xffffffffu;
    }
}
'@
}

function Wait-Line([string]$Expected) {
    $taskDeadline = [DateTime]::UtcNow.AddSeconds(30)
    while ([DateTime]::UtcNow -lt $taskDeadline) {
        $taskLine = $taskSerial.ReadLine().TrimEnd("`r")
        if ($taskLine -eq $Expected) { return }
        if ($taskLine.StartsWith('RX_RETRY')) { throw 'Block CRC failed; receiver will time out safely' }
    }
    throw "Missing acknowledgement: $Expected"
}

try {
    $taskSerial.Open()
    $taskSerial.Write(([string][char]3) + "`n")
    Start-Sleep -Milliseconds 250
    $taskSerial.DiscardInBuffer()
    $taskSerial.WriteLine('echo RX_SHELL_READY')
    Wait-Line 'RX_SHELL_READY'
    $taskSerial.WriteLine("python3 /opt/aco-sidecar/serial_receive_checked.py $RemotePath $($taskBytes.Length) $taskHash $TransferBaudRate")
    Wait-Line 'RX_READY'
    $taskSerial.WriteLine('GO')
    Start-Sleep -Milliseconds 100
    $taskSerial.BaudRate = $TransferBaudRate
    Wait-Line 'RX_START'
    $taskResumeLine = $taskSerial.ReadLine().TrimEnd("`r")
    if ($taskResumeLine -notmatch '^RX_RESUME ([0-9]+) ([0-9a-f]{64})$') { throw 'Invalid resume response' }
    $taskResumeOffset = [int]$Matches[1]
    $taskResumeHash = $Matches[2]
    if ($taskResumeOffset -gt $taskBytes.Length -or ($taskResumeOffset -ne $taskBytes.Length -and $taskResumeOffset % 4096)) {
        throw 'Invalid resume boundary'
    }
    $taskHasher = [Security.Cryptography.SHA256]::Create()
    try { $taskPrefixHash = [BitConverter]::ToString($taskHasher.ComputeHash($taskBytes,0,$taskResumeOffset)).Replace('-','').ToLowerInvariant() }
    finally { $taskHasher.Dispose() }
    if ($taskPrefixHash -ne $taskResumeHash) { throw 'Partial file differs from local prefix; refusing resume' }
    Write-Output "Verified resume prefix: $taskResumeOffset bytes"
    $taskSequence = [Math]::Floor($taskResumeOffset / 4096)
    $taskLastProgress = -10
    for ($taskOffset = $taskResumeOffset; $taskOffset -lt $taskBytes.Length; $taskOffset += 4096) {
        $taskLength = [Math]::Min(4096, $taskBytes.Length - $taskOffset)
        $taskCrc = [AcoSerialCrc32]::Compute($taskBytes, $taskOffset, $taskLength)
        $taskEncoded = [Convert]::ToBase64String($taskBytes, $taskOffset, $taskLength)
        $taskSerial.WriteLine("$taskSequence $($taskCrc.ToString('x8')) $taskEncoded")
        Wait-Line "RX_ACK $taskSequence"
        $taskSequence++
        $taskProgress = [Math]::Floor(100.0 * ($taskOffset + $taskLength) / $taskBytes.Length)
        if ($taskProgress -ge $taskLastProgress + 10) {
            Write-Output "Acknowledged $taskProgress%"
            $taskLastProgress = $taskProgress
        }
    }
    Wait-Line "RX_DONE $taskHash"
    $taskSerial.WriteLine('BYE')
    Start-Sleep -Milliseconds 250
    $taskSerial.BaudRate = 115200
    Write-Output "Board verified SHA256: $taskHash"
} finally {
    if ($taskSerial.IsOpen) { $taskSerial.Close() }
    $taskSerial.Dispose()
}

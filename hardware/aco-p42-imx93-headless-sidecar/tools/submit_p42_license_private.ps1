param(
    [Parameter(Mandatory = $true)][string]$SecretFile,
    [string]$PortName = 'COM3',
    [switch]$ProvisionOnBoard,
    [switch]$VerifyBoardCopy
)
$ErrorActionPreference = 'Stop'
if ($ProvisionOnBoard -and $VerifyBoardCopy) { throw 'Choose provision or verify, not both' }
$taskSecretPath = (Resolve-Path -LiteralPath $SecretFile).Path
$taskProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ($taskSecretPath.StartsWith($taskProjectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'License must be outside the project directory'
}
$taskAncestor = [IO.DirectoryInfo]::new([IO.Path]::GetDirectoryName($taskSecretPath))
while ($null -ne $taskAncestor) {
    if (Test-Path -LiteralPath (Join-Path $taskAncestor.FullName '.git')) { throw 'License must be outside Git' }
    $taskAncestor = $taskAncestor.Parent
}
$taskSecretBytes = $null
$taskPayload = $null
$taskFrame = $null
$taskSerial = [IO.Ports.SerialPort]::new($PortName,115200,'None',8,'One')
$taskSerial.NewLine = "`n"
$taskSerial.ReadTimeout = 25000
$taskSerial.WriteTimeout = 3000
$taskSerial.DtrEnable = $false
$taskSerial.RtsEnable = $false
function Wait-PrivateLine([string]$Expected) {
    $taskDeadline = [DateTime]::UtcNow.AddSeconds(25)
    while ([DateTime]::UtcNow -lt $taskDeadline) {
        $taskLine = $taskSerial.ReadLine().TrimEnd("`r")
        if ($taskLine -eq $Expected) { return }
        if ($taskLine -eq 'LICENSE_DELIVERY_FAILED') { throw 'Board-local License delivery failed' }
        if ($taskLine -eq 'LICENSE_BOARD_COPY_MISMATCH') { throw 'Board copy differs from private host file; no content exposed' }
    }
    throw 'Private License channel timed out'
}
try {
    $taskSecretBytes = [IO.File]::ReadAllBytes($taskSecretPath)
    $taskBegin = 0
    if ($taskSecretBytes.Length -ge 3 -and $taskSecretBytes[0] -eq 239 -and $taskSecretBytes[1] -eq 187 -and $taskSecretBytes[2] -eq 191) { $taskBegin = 3 }
    $taskEnd = $taskSecretBytes.Length
    while ($taskEnd -gt $taskBegin -and $taskSecretBytes[$taskEnd-1] -in 10,13) { $taskEnd-- }
    $taskLength = $taskEnd - $taskBegin
    if ($taskLength -lt 1 -or $taskLength -gt 256) { throw 'Invalid License file format' }
    $taskPayload = [byte[]]::new($taskLength)
    [Array]::Copy($taskSecretBytes,$taskBegin,$taskPayload,0,$taskLength)
    if ($taskPayload -contains 0 -or $taskPayload -contains 10 -or $taskPayload -contains 13) { throw 'License file must contain one UTF-8 line' }
    $taskFrame = [byte[]]::new($taskLength+2)
    $taskFrame[0] = [byte]($taskLength -shr 8)
    $taskFrame[1] = [byte]($taskLength -band 255)
    [Array]::Copy($taskPayload,0,$taskFrame,2,$taskLength)
    $taskSerial.Open()
    $taskSerial.Write(([string][char]3) + "`n")
    Start-Sleep -Milliseconds 250
    $taskSerial.DiscardInBuffer()
    $taskReceiverCommand = 'python3 /opt/aco-sidecar/serial_submit_license.py'
    if ($ProvisionOnBoard) { $taskReceiverCommand += ' --provision' }
    if ($VerifyBoardCopy) { $taskReceiverCommand += ' --verify-only' }
    $taskSerial.WriteLine($taskReceiverCommand)
    Wait-PrivateLine 'LICENSE_INPUT_READY'
    # Binary write occurs only after the board disables echo; never shell arguments.
    $taskSerial.Write($taskFrame,0,$taskFrame.Length)
    if ($VerifyBoardCopy) {
        Wait-PrivateLine 'LICENSE_BOARD_COPY_MATCH'
        Write-Output 'Board private License matches private host file; no content or digest exposed; no IPC/state change.'
    } else {
        Wait-PrivateLine 'LICENSE_IPC_DELIVERED'
        Write-Output 'License delivered through private board-local IPC; connection not yet verified.'
    }
} finally {
    foreach ($taskBuffer in @($taskSecretBytes,$taskPayload,$taskFrame)) {
        if ($null -ne $taskBuffer) { [Array]::Clear($taskBuffer,0,$taskBuffer.Length) }
    }
    if ($taskSerial.IsOpen) { $taskSerial.Close() }
    $taskSerial.Dispose()
}

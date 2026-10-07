# The actual License is supplied only through a local masked prompt, never source.
$ErrorActionPreference = 'Stop'
$taskSecretDirectory = Join-Path (Join-Path $env:ProgramData 'AcoSidecarSecrets') $env:USERNAME
$taskSecretPath = Join-Path $taskSecretDirectory 'p42.license'
$taskAncestor = [IO.DirectoryInfo]::new($taskSecretDirectory)
while ($null -ne $taskAncestor) {
    if (Test-Path -LiteralPath (Join-Path $taskAncestor.FullName '.git')) {
        throw 'Private License directory must be outside Git before prompting'
    }
    $taskAncestor = $taskAncestor.Parent
}
if (Test-Path -LiteralPath $taskSecretPath) {
    throw "Private License file already exists; refusing to overwrite: $taskSecretPath"
}
$null = New-Item -ItemType Directory -Path $taskSecretDirectory -Force
$taskAcl = Get-Acl -LiteralPath $taskSecretDirectory
$taskAcl.SetAccessRuleProtection($true,$false)
$taskIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().User
$taskSystem = [Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$taskInheritance = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
foreach ($taskPrincipal in @($taskIdentity,$taskSystem)) {
    $taskRule = [Security.AccessControl.FileSystemAccessRule]::new($taskPrincipal,[Security.AccessControl.FileSystemRights]::FullControl,$taskInheritance,[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
    $taskAcl.AddAccessRule($taskRule)
}
Set-Acl -LiteralPath $taskSecretDirectory -AclObject $taskAcl
$taskSecure = $null
$taskPointer = [IntPtr]::Zero
$taskUtf8 = $null
try {
    Write-Output "Private file: $taskSecretPath"
    $taskSecure = Read-Host 'P42 License (masked; do not paste into chat)' -AsSecureString
    $taskPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($taskSecure)
    $taskPlain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($taskPointer)
    $taskUtf8 = [Text.Encoding]::UTF8.GetBytes($taskPlain)
    $taskPlain = $null
    if ($taskUtf8.Length -lt 1 -or $taskUtf8.Length -gt 256 -or $taskUtf8 -contains 0 -or $taskUtf8 -contains 10 -or $taskUtf8 -contains 13) {
        throw 'Invalid single-line License input'
    }
    $taskFile = [IO.File]::Open($taskSecretPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $taskFile.Write($taskUtf8,0,$taskUtf8.Length); $taskFile.Flush($true) }
    finally { $taskFile.Dispose() }
} finally {
    if ($null -ne $taskUtf8) { [Array]::Clear($taskUtf8,0,$taskUtf8.Length) }
    if ($taskPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($taskPointer) }
    if ($null -ne $taskSecure) { $taskSecure.Dispose() }
}
& (Join-Path $PSScriptRoot 'submit_p42_license_private.ps1') -SecretFile $taskSecretPath

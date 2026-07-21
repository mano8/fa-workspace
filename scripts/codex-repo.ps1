[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string[]] $Repository,

    [string[]] $Task = @(),

    [string[]] $Operation = @(),

    [string[]] $Authorization = @(),

    [string] $AuthorizationExternalRoot,

    [string] $AuthorizationTrustStore,

    [string] $AuthorizationReplayStore,

    [switch] $PrepareAuthorizationRequest,

    [string] $ResumeRuntime,

    [string] $Fresh,

    [Nullable[int]] $CleanupRetained,

    [Parameter(Mandatory, Position = 0, ValueFromRemainingArguments = $true)]
    [string] $Prompt
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$lifecycleSelections = @($ResumeRuntime, $Fresh) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
if ($lifecycleSelections.Count -gt 1) {
    throw "ResumeRuntime and Fresh are mutually exclusive."
}

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$pythonCommand = if (-not [string]::IsNullOrWhiteSpace($env:M8_PYTHON)) {
    $env:M8_PYTHON
} else {
    "python"
}
$originalPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$workspaceRoot/scripts" + $(if ($originalPythonPath) { ";$originalPythonPath" } else { "" })

Push-Location -LiteralPath $workspaceRoot
try {
    $arguments = @("-m", "agent_context.codex_repo_launcher")
    foreach ($item in $Repository) { $arguments += @("--repository", $item) }
    foreach ($item in $Task) { $arguments += @("--task", $item) }
    foreach ($item in $Operation) { $arguments += @("--operation", $item) }
    foreach ($item in $Authorization) { $arguments += @("--authorization", $item) }
    if ($AuthorizationExternalRoot) { $arguments += @("--authorization-external-root", $AuthorizationExternalRoot) }
    if ($AuthorizationTrustStore) { $arguments += @("--authorization-trust-store", $AuthorizationTrustStore) }
    if ($AuthorizationReplayStore) { $arguments += @("--authorization-replay-store", $AuthorizationReplayStore) }
    if ($PrepareAuthorizationRequest) { $arguments += "--prepare-authorization-request" }
    if ($ResumeRuntime) { $arguments += @("--resume-runtime", $ResumeRuntime) }
    if ($Fresh) { $arguments += @("--fresh", $Fresh) }
    if ($null -ne $CleanupRetained) { $arguments += @("--cleanup-retained", $CleanupRetained.Value) }
    $arguments += $Prompt
    & $pythonCommand @arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
    $env:PYTHONPATH = $originalPythonPath
}

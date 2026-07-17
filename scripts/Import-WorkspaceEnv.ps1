[CmdletBinding()]
param(
    [ValidateSet("local", "devcontainer")]
    [string] $Profile,

    [switch] $ValidateOnly,

    [switch] $SkipAvailability
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $PSBoundParameters.ContainsKey("Profile")) {
    $insideContainer = (Test-Path -LiteralPath "/.dockerenv") -or
        -not [string]::IsNullOrWhiteSpace($env:REMOTE_CONTAINERS)
    $Profile = if ($insideContainer) { "devcontainer" } else { "local" }
}

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$profileFile = Join-Path $workspaceRoot ".env.$Profile"
$exampleFile = "$profileFile.example"

if (-not (Test-Path -LiteralPath $profileFile -PathType Leaf)) {
    throw "Missing workspace profile '$profileFile'. Copy '$exampleFile' and configure it locally."
}

$values = [ordered] @{}
$lineNumber = 0

foreach ($rawLine in Get-Content -LiteralPath $profileFile) {
    $lineNumber += 1
    $line = $rawLine.Trim()

    if ($line.Length -eq 0 -or $line.StartsWith("#")) {
        continue
    }

    $separator = $line.IndexOf("=")
    if ($separator -le 0) {
        throw "Invalid environment entry at line $lineNumber in '$profileFile'."
    }

    $key = $line.Substring(0, $separator).Trim()
    $value = $line.Substring($separator + 1).Trim()

    if ($key -notmatch "^[A-Z][A-Z0-9_]*$") {
        throw "Invalid environment key at line $lineNumber in '$profileFile'."
    }

    if (
        $value.Length -ge 2 -and
        (($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'")))
    ) {
        $value = $value.Substring(1, $value.Length - 2)
    }

    if ($values.Contains($key)) {
        throw "Duplicate environment key '$key' in '$profileFile'."
    }

    $values[$key] = $value
}

$required = @(
    "M8_WORKSPACE_ROOT",
    "M8_RUNTIME",
    "M8_HOST_OS",
    "M8_PYTHON_ENV_KIND",
    "M8_JS_RUNTIME_KIND",
    "M8_PACKAGE_MANAGER_KIND",
    "M8_VCS_KIND",
    "M8_CONTAINER_ENGINE_KIND",
    "M8_COMPOSE_KIND"
)

foreach ($key in $required) {
    if (
        -not $values.Contains($key) -or
        [string]::IsNullOrWhiteSpace($values[$key]) -or
        $values[$key] -eq "changethis"
    ) {
        throw "Required environment key '$key' is missing or not configured in '$profileFile'."
    }
}

$expectedRuntime = if ($Profile -eq "local") { "local" } else { "devcontainer" }
if ($values["M8_RUNTIME"] -ne $expectedRuntime) {
    throw "Profile '$Profile' must set M8_RUNTIME=$expectedRuntime."
}

if ($values["M8_HOST_OS"] -notin @("windows", "linux", "macos")) {
    throw "M8_HOST_OS must be windows, linux, or macos."
}

if ($Profile -eq "devcontainer" -and $values["M8_HOST_OS"] -ne "linux") {
    throw "The devcontainer profile must set M8_HOST_OS=linux."
}

$toolGroups = @(
    @{
        KindKey = "M8_PYTHON_ENV_KIND"
        CommandKey = "M8_PYTHON"
        Allowed = @("conda", "venv", "virtualenv", "uv", "poetry", "pipenv", "pyenv", "system", "other", "none")
    },
    @{
        KindKey = "M8_JS_RUNTIME_KIND"
        CommandKey = "M8_JS_RUNTIME"
        Allowed = @("node", "bun", "deno", "other", "none")
    },
    @{
        KindKey = "M8_PACKAGE_MANAGER_KIND"
        CommandKey = "M8_PACKAGE_MANAGER"
        Allowed = @("npm", "pnpm", "yarn", "bun", "other", "none")
    },
    @{
        KindKey = "M8_VCS_KIND"
        CommandKey = "M8_VCS"
        Allowed = @("git", "other")
    },
    @{
        KindKey = "M8_CONTAINER_ENGINE_KIND"
        CommandKey = "M8_CONTAINER_ENGINE"
        Allowed = @("docker", "podman", "other", "none")
    },
    @{
        KindKey = "M8_COMPOSE_KIND"
        CommandKey = "M8_COMPOSE"
        Allowed = @("docker-plugin", "docker-compose", "podman-compose", "other", "none")
    }
)

$commandsToCheck = @()
foreach ($group in $toolGroups) {
    $kindKey = $group.KindKey
    $commandKey = $group.CommandKey
    $kind = $values[$kindKey]
    $command = if ($values.Contains($commandKey)) { $values[$commandKey] } else { "" }

    if ($kind -notin $group.Allowed) {
        throw "Unsupported tool kind configured for '$kindKey'."
    }

    if ($kind -eq "none") {
        if (-not [string]::IsNullOrWhiteSpace($command)) {
            throw "Tool command '$commandKey' must be empty when '$kindKey' is none."
        }
    } elseif ([string]::IsNullOrWhiteSpace($command) -or $command -eq "changethis") {
        throw "Tool command '$commandKey' must be configured when '$kindKey' is enabled."
    } else {
        $commandsToCheck += $commandKey
    }
}

foreach ($optionalCommand in @("M8_PYTHON_MANAGER", "M8_PACKAGE_EXECUTOR")) {
    if (
        $values.Contains($optionalCommand) -and
        -not [string]::IsNullOrWhiteSpace($values[$optionalCommand])
    ) {
        if ($values[$optionalCommand] -eq "changethis") {
            throw "Optional command '$optionalCommand' is not configured."
        }
        $commandsToCheck += $optionalCommand
    }
}

foreach ($entry in $values.GetEnumerator()) {
    if ($entry.Key -like "M8_TOOL_*") {
        if ([string]::IsNullOrWhiteSpace($entry.Value) -or $entry.Value -eq "changethis") {
            throw "Additional tool '$($entry.Key)' is declared but not configured."
        }
        $commandsToCheck += $entry.Key
    }
}

function Assert-WorkspaceCommand {
    param(
        [Parameter(Mandatory)]
        [string] $Key
    )

    $command = $values[$Key]
    $isPath = [System.IO.Path]::IsPathRooted($command)
    $isAvailable = if ($isPath) {
        Test-Path -LiteralPath $command -PathType Leaf
    } else {
        $null -ne (Get-Command $command -ErrorAction SilentlyContinue)
    }

    if (-not $isAvailable) {
        throw "Configured command '$Key' is not available."
    }
}

if (-not $SkipAvailability) {
    if (-not (Test-Path -LiteralPath $values["M8_WORKSPACE_ROOT"] -PathType Container)) {
        throw "M8_WORKSPACE_ROOT does not resolve to a directory."
    }

    foreach ($key in $commandsToCheck) {
        Assert-WorkspaceCommand -Key $key
    }
}

if (-not $ValidateOnly) {
    foreach ($entry in $values.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
    }
}

$mode = if ($ValidateOnly) { "validated" } else { "loaded" }
Write-Host "Workspace environment profile '$Profile' $mode successfully."

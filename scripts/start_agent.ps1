<#
Launcher contract:
- This entrypoint starts the workflow immediately.
- If invoked after `AGENT.md` review or from a `Start AGENT.md` style trigger, do not wait for a second confirmation prompt.
#>

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$envPath = Join-Path $repoRoot '.env'

function Import-DotEnv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }

        $parts = $trimmed -split '=', 2
        if ($parts.Count -ne 2) {
            continue
        }

        $name = $parts[0].Trim()
        $value = $parts[1].Trim()

        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}

Import-DotEnv -Path $envPath

$pythonCommand = if ($env:AGENT_PYTHON_COMMAND) { $env:AGENT_PYTHON_COMMAND } else { 'python' }
$workflowScript = Join-Path $repoRoot 'scripts\run_workflow.py'

if ($env:AGENT_START_COMMAND) {
    $command = $env:AGENT_START_COMMAND
} else {
    $recencyHours = if ($env:AGENT_START_RECENCY_HOURS) { $env:AGENT_START_RECENCY_HOURS } else { '24' }
    $command = "$pythonCommand `"$workflowScript`" --recency-hours $recencyHours"
}

Push-Location $repoRoot
try {
    Write-Host 'AGENT.md/workflow review complete -> starting workflow automatically...'
    Invoke-Expression $command
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

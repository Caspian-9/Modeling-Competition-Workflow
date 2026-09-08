[CmdletBinding()]
param(
    [string]$CaseId,
    [string[]]$Questions = @("Q1", "Q2", "Q3", "Q4")
)

$ErrorActionPreference = "Stop"
$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $workspace
$env:PYTHONUTF8 = "1"

if ([string]::IsNullOrWhiteSpace($CaseId)) {
    $CaseId = Read-Host "Case ID"
}
$CaseId = $CaseId.Trim()
foreach ($dash in @([char]0x2014, [char]0x2013, [char]0xFF0D, [char]0x2212)) {
    $CaseId = $CaseId.Replace($dash, [char]0x002D)
}
$CaseId = $CaseId -replace '\s+', '-'

$caseConfig = Join-Path $workspace ("cases\" + $CaseId + "\case.json")
if (-not (Test-Path -LiteralPath $caseConfig -PathType Leaf)) {
    & python -m harness init $CaseId --questions $Questions
    if ($LASTEXITCODE -ne 0) {
        throw "FAST case initialization failed."
    }
}

& python -m harness intake $CaseId
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Raw intake is not ready. Put one problem PDF and at least one data file in cases\$CaseId\raw\."
}

$codexExecutable = $null
if (
    -not [string]::IsNullOrWhiteSpace($env:HARNESS_CODEX_EXECUTABLE) -and
    (Test-Path -LiteralPath $env:HARNESS_CODEX_EXECUTABLE -PathType Leaf)
) {
    $codexExecutable = $env:HARNESS_CODEX_EXECUTABLE
}
if ($null -eq $codexExecutable) {
    $command = Get-Command codex.cmd -CommandType Application -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        $codexExecutable = $command.Source
    }
}
if ($null -eq $codexExecutable) {
    $npmWrapper = Join-Path $env:APPDATA "npm\codex.cmd"
    if (Test-Path -LiteralPath $npmWrapper -PathType Leaf) {
        $codexExecutable = $npmWrapper
    }
}
if ($null -eq $codexExecutable) {
    throw "Codex CLI was not found. Install it or set HARNESS_CODEX_EXECUTABLE."
}

$prompt = @"
Read AGENTS.md and .agents/skills/orchestrate-modeling-work/SKILL.md first.
Act as the persistent lead modeling Agent for case '$CaseId', not as a Supervisor.
Use Simplified Chinese for all user-facing communication and artifacts.
Read the FAST workspace files, solve the modeling problem continuously, and invoke Engineer, Librarian, Judge, or Writer skills only when they add value.
Do not use legacy state, agent_jobs, checkpoints, requests, supervision, or agent-dispatch.
Keep Harness metadata and logs out of the paper.
"@

& $codexExecutable --cd $workspace --model gpt-5.6-terra `
    -c 'model_reasoning_effort="high"' $prompt
exit $LASTEXITCODE

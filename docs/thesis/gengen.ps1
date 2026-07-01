# Generate both HTML and PDF outputs for one Markdown file.
param(
    [string]$file = $(throw "File is required."),
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs = @()
)
$DebugPreference = "Continue"
$ErrorActionPreference = "Stop"

# file exists?
if (-not (Test-Path $file)) {
    Write-Error "File not found: $file"
    exit 1
}

$file = (Resolve-Path $file).Path
$resourcePath = [System.IO.Path]::GetDirectoryName($file)

$needsAgentResults = Select-String -LiteralPath $file -SimpleMatch "include-agent-challenge-results" -Quiet
if ($needsAgentResults) {
    $evaluationGenerator = Join-Path $PSScriptRoot "generate_agent_challenge_evaluation.py"
    & uv run python $evaluationGenerator
    if ($LASTEXITCODE -ne 0) {
        throw "agent challenge evaluation generation failed with exit code $LASTEXITCODE"
    }
}

# name without extension
function Get-OutputFilenames([string] $file, [string] $type) {
    $parentdir = [System.IO.Path]::GetDirectoryName($file)
    if (-not $parentdir) { $parentdir = '.' }
    $filename = [System.IO.Path]::GetFileNameWithoutExtension($file)
    $newfilename = "${filename}.${type}"
    return Join-Path $parentdir $newfilename
}

Write-Host "Generating HTML and PDF for $file..."
Write-Debug "Remaining args: $($RemainingArgs | Format-List)"

& $PSScriptRoot\generate.ps1 -type html -- -i $file -o (Get-OutputFilenames $file "html") --resource-path $resourcePath @RemainingArgs

& $PSScriptRoot\generate.ps1 -type pdf -- -i $file -o (Get-OutputFilenames $file "pdf") --resource-path $resourcePath @RemainingArgs

# Generate both HTML and PDF outputs for one Markdown file.
param(
    [string]$file = $(throw "File is required."),
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs = @()
)
$DebugPreference = "Continue"

# file exists?
if (-not (Test-Path $file)) {
    Write-Error "File not found: $file"
    exit 1
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

& $PSScriptRoot\generate.ps1 -type html -- -i $file -o (Get-OutputFilenames $file "html") @RemainingArgs

& $PSScriptRoot\generate.ps1 -type pdf -- -i $file -o (Get-OutputFilenames $file "pdf") @RemainingArgs

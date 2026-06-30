# goal:
# use pandoc -M to change the key: diagram:engine:mermaid:outputFormat to svg or pdf if output is html or pdf.
# use the script at stuff/pandoc-diagram.ps1 to set the env vars and pass the filter to pandoc.
param(
    [string]$type,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)
function New-PandocDiagramMetadata([string] $outputFormat) {
    return @{
        "diagram" = @{
            "engine" = @{
                "mermaid" = @{
                    "outputFormat" = "$outputFormat"
                }
            }
        }
    }
} 
# 
if ($type -eq "html") {
    $outputFormat = "svg"
}
elseif ($type -eq "pdf") {
    $outputFormat = "pdf"
}
else {
    Write-Error "Unsupported type: $type. Supported types are: html, pdf."
    exit 1
}

$metadata = New-PandocDiagramMetadata $outputFormat | ConvertTo-Json -Depth 10
$pandoc_diagram = Join-Path $PSScriptRoot "../../stuff/pandoc-diagram.ps1"
if (-not (Test-Path $pandoc_diagram)) {
    Write-Error "pandoc diagram wrapper not found at $pandoc_diagram. Make sure it exists, then rerun this command."
    exit 1
}
. $pandoc_diagram

$pandoc_crossref = Get-Command pandoc-crossref -ErrorAction SilentlyContinue
if (-not $pandoc_crossref) {
    Write-Error "pandoc-crossref is required for Figure cross-references. Install it, then rerun this command."
    exit 1
}

$diagram_filter = Join-Path $PSScriptRoot "../../stuff/diagram.lua"
if (-not (Test-Path $diagram_filter)) {
    Write-Error "diagram.lua filter not found at $diagram_filter. Make sure it exists, then rerun this command."
    exit 1
}

$figure_format_filter = Join-Path $PSScriptRoot "figure-format.lua"
if (-not (Test-Path $figure_format_filter)) {
    Write-Error "figure-format.lua filter not found at $figure_format_filter. Make sure it exists, then rerun this command."
    exit 1
}

$include_markdown_filter = Join-Path $PSScriptRoot "include-markdown.lua"
if (-not (Test-Path $include_markdown_filter)) {
    Write-Error "include-markdown.lua filter not found at $include_markdown_filter. Make sure it exists, then rerun this command."
    exit 1
}

$agent_results = Join-Path $PSScriptRoot "agent-challenge-results.md"
if (-not (Test-Path $agent_results)) {
    Write-Error "agent-challenge-results.md is missing. Run generate_agent_challenge_evaluation.py first."
    exit 1
}

$title_pages_header = Join-Path $PSScriptRoot "title-pages.tex"
if (-not (Test-Path $title_pages_header)) {
    Write-Error "title-pages.tex is missing. Make sure the thesis front matter header exists."
    exit 1
}
$title_pages_args = @()
if ($type -eq "pdf") {
    $title_pages_args = @("--include-in-header", $title_pages_header)
}


$metatempfile = New-TemporaryFile
$pandocExitCode = 0

try {
    Set-Content -Path $metatempfile -Value $metadata
    pandoc `
        --lua-filter $include_markdown_filter `
        --lua-filter $diagram_filter `
        --lua-filter $figure_format_filter `
        --filter=pandoc-crossref `
        --pdf-engine=xelatex `
        @title_pages_args `
        --metadata thesisFigureFormat=$outputFormat `
        --metadata thesisAgentResults=$agent_results `
        --metadata-file=$metatempfile `
        --embed-resources --standalone --citeproc `
        @RemainingArgs
    $pandocExitCode = $LASTEXITCODE
}
finally {
    Remove-Item $metatempfile
}

if ($pandocExitCode -ne 0) {
    throw "pandoc failed with exit code $pandocExitCode"
}

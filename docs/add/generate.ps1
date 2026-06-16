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


$metatempfile = New-TemporaryFile

try {
    Set-Content -Path $metatempfile -Value $metadata
    pandoc `
        --lua-filter $diagram_filter `
        --filter=pandoc-crossref `
        --pdf-engine=xelatex `
        --metadata-file=$metatempfile `
        --embed-resources --standalone --citeproc `
        @RemainingArgs
}
finally {
    Remove-Item $metatempfile
}

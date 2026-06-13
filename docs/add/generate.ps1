# goal:
# use pandoc -M to change the key: diagram:engine:mermaid:outputFormat to svg or pdf if output is html or pdf.
# use the script at stuff/pandoc-diagram.ps1 to set the env vars and pass the filter to pandoc.
param(
    [string]$type,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)
function funny([string] $output) {
    return @{
        "diagram" = @{
            "engine" = @{
                "mermaid" = @{
                    "outputFormat" = "$output"
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

$metadata = funny $outputFormat | ConvertTo-Json -Depth 10
$pandoc_diagram = Join-Path $PSScriptRoot "../../stuff/pandoc-diagram.ps1"

$metatempfile = New-TemporaryFile

try {
    Set-Content -Path $metatempfile -Value $metadata
    & $pandoc_diagram --metadata-file=$metatempfile --embed-resources --standalone @RemainingArgs
}
finally {
    Remove-Item $metatempfile
}

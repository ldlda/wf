<#
.SYNOPSIS
    pandoc wrapper with diagram.lua filter, mermaid, and tikz/xelatex support.
.DESCRIPTION
    Sets MERMAID_BIN, TIKZ_BIN, and passes --lua-filter diagram.lua to pandoc.
    All other arguments are forwarded to pandoc.
.EXAMPLE
    .\pandoc-diagram.ps1 -- input.md -o output.pdf
    .\pandoc-diagram.ps1 -- input.md -o output.html --embed-resources
    .\pandoc-diagram.ps1 -- input.md -o output.pdf --pdf-engine=xelatex
#>
function whereis($cmd) { Get-Command $cmd -CommandType Application | select-object -ExpandProperty Path -First 1 }

$filter = Join-Path $PSScriptRoot 'diagram.lua'

$env:MERMAID_BIN = whereis mmdc
$env:TIKZ_BIN = 'xelatex'

Write-Host @args

& pandoc --lua-filter $filter --pdf-engine=xelatex @args

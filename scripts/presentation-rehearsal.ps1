[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:5173",
    [string]$OutputRoot = "web/apps/console/.visual-smoke/rehearsal",
    [string[]]$Viewports = @("1280,720", "1024,768")
)

$ErrorActionPreference = "Stop"
$ManifestPath = Join-Path $PSScriptRoot "presentation-rehearsal-routes.json"

try {
    Invoke-WebRequest -Uri $BaseUrl -UseBasicParsing -TimeoutSec 5 | Out-Null
}
catch {
    throw "Presentation dev server unavailable at $BaseUrl. Start it with: pnpm --dir web dev"
}

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "Presentation rehearsal route manifest not found: $ManifestPath"
}

$Routes = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($null -eq $Routes -or @($Routes).Count -eq 0) {
    throw "Presentation rehearsal route manifest is empty: $ManifestPath"
}

foreach ($Viewport in $Viewports) {
    $ViewportRoot = Join-Path $OutputRoot $Viewport
    New-Item -ItemType Directory -Path $ViewportRoot -Force | Out-Null

    foreach ($Route in $Routes) {
        if ([string]::IsNullOrWhiteSpace($Route.route) -or [string]::IsNullOrWhiteSpace($Route.fileStem)) {
            throw "Each rehearsal route must define both route and fileStem: $($Route | ConvertTo-Json -Compress)"
        }

        $FileName = (($Route.fileStem -replace '[^A-Za-z0-9._-]', '-') + ".png")
        $Url = "$($BaseUrl.TrimEnd('/'))/present#scene/$($Route.route)"
        $OutputPath = Join-Path $ViewportRoot $FileName

        Write-Host "$Viewport $Url -> $OutputPath"
        & pnpx --yes playwright screenshot `
            --viewport-size $Viewport `
            --wait-for-timeout 800 `
            $Url `
            $OutputPath
        if ($LASTEXITCODE -ne 0) {
            throw "Screenshot capture failed for $Url at $Viewport (exit code $LASTEXITCODE)"
        }
    }
}

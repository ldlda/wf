param(
    [string]$AttachUrl = "http://127.0.0.1:8192",
    [int]$Trials = 5,
    [int]$Concurrency = 2,
    [int]$TimeoutSeconds = 3600,
    [object[]]$models = @( # object[] because ModelProfile is not known yet
        [ModelProfile]::new("opencode/deepseek-v4-flash-free", "max"),
        [ModelProfile]::new("opencode/mimo-v2.5-free", "high"),
        [ModelProfile]::new("opencode/nemotron-3-ultra-free", "high")
    )
)

class ModelProfile {
    [string]$Model
    [string]$Variant

    ModelProfile([string]$model, [string]$variant) {
        $this.Model = $model
        $this.Variant = $variant
    }

    [string]ToString() {
        return "$($this.Model) ($($this.Variant))"
    }

    ModelProfile() {}
}

function New-ModelProfile([string]$model, [string]$variant) {
    return [ModelProfile]::new($model, $variant)
}

$ErrorActionPreference = "Stop"

[ModelProfile[]]$models = $models # cast should fail if there are any non-ModelProfile objects in the array

Push-Location (Get-Item $PSScriptRoot).Parent.Parent.FullName

try {
    $argsList = @(
        "run",
        "python",
        "examples/agent_challenges/run_matrix.py",
        "--trials",
        "$Trials",
        "--concurrency",
        "$Concurrency",
        "--attach",
        "$AttachUrl",
        "--timeout-seconds",
        "$TimeoutSeconds"
    )
    foreach ($model in $models) {
        $argsList += "--model"
        $argsList += "$($model.Model)=$($model.Variant)"
    }
    uv @argsList
}
finally {
    Pop-Location
}

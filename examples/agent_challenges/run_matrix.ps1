param(
    [string]$AttachUrl = "http://127.0.0.1:8192",
    [int]$Trials = 5,
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

# Run from the repository root no matter where the script is invoked.
Set-Location (Get-Item $PSScriptRoot).Parent.Parent.FullName

$profiles = @(
    "none",
    "skills",
    "all"
)

$challenges = @(
    "examples/agent_challenges/browser_click_challenge/challenge.yaml",
    "examples/agent_challenges/report_workflow_challenge/challenge.yaml"
)

foreach ($challenge in $challenges) {
    foreach ($challengeProfile in $profiles) {
        foreach ($model in $models) {
            Write-Host ""
            Write-Host "==> challenge=$challenge profile=$challengeProfile model=$model trials=$Trials"
            uv run python examples/agent_challenges/run_trials.py `
                --challenge $challenge `
                --instruction-profile $challengeProfile `
                --model $model.Model `
                --variant $model.Variant `
                --trials $Trials `
                --attach $AttachUrl `
                --timeout-seconds $TimeoutSeconds
        }
    }
}

Pop-Location

# Opencode Browser Click Challenge Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local evidence harness that runs the browser-click workflow challenge through `opencode run`, captures trial outputs, and classifies failures without changing product runtime code.

**Architecture:** The harness lives under `examples/agent_challenges/browser_click_challenge/` and treats opencode as an external executable. Tests do not call opencode; they cover prompt loading, command construction, JSONL/result parsing, and deterministic classification from captured text.

**Tech Stack:** Python stdlib (`argparse`, `json`, `subprocess`, `dataclasses`, `pathlib`, `time`), pytest, existing browser-click workflow example, optional Playwright MCP attachment configured by command-line flags.

---

## File Structure

- Create `examples/agent_challenges/browser_click_challenge/prompt.md`
  - The exact prompt sent to agents.
  - It must require workflow usage, deployment run, before/after snapshots, cleanup, and final summary.
- Create `examples/agent_challenges/browser_click_challenge/README.md`
  - How to prepare the local server/config.
  - How to run one trial and multiple trials.
  - How to attach Playwright MCP when desired.
  - How success/failure is classified.
- Create `examples/agent_challenges/browser_click_challenge/results/.gitignore`
  - Keeps the output folder in git.
  - Ignores generated trial outputs in the folder itself.
- Create `examples/agent_challenges/browser_click_challenge/run_opencode_trials.py`
  - CLI harness.
  - Builds `opencode run` command.
  - Runs N trials.
  - Writes one JSON artifact per trial.
  - Classifies result text.
- Create `tests/examples/test_opencode_browser_click_challenge.py`
  - Unit tests only.
  - No live opencode calls.
- Modify `docs/add/evidence-index.md`
  - Add the challenge harness as planned/evaluation evidence.
- Modify `docs/current_roadmap.md`
  - Add completed evidence-harness bullet after implementation.

---

## Task 1: Add Prompt And README

**Files:**
- Create: `examples/agent_challenges/browser_click_challenge/prompt.md`
- Create: `examples/agent_challenges/browser_click_challenge/README.md`
- Create: `examples/agent_challenges/browser_click_challenge/results/.gitignore`
- Test: no pytest yet; this task is docs/assets only

- [ ] **Step 1: Create challenge folder**

Run:

```powershell
New-Item -ItemType Directory -Force examples\agent_challenges\browser_click_challenge\results
New-Item -ItemType File -Force examples\agent_challenges\browser_click_challenge\results\.gitignore
```

Expected: the folder exists.

- [ ] **Step 2: Create prompt**

Create `examples/agent_challenges/browser_click_challenge/prompt.md`:

```markdown
# Browser Click Workflow Challenge

Build and successfully run a workflow that:

1. Opens a browser page or local web page with a visible button.
2. Waits for a human click or performs a clearly simulated click.
3. Captures a before snapshot and an after snapshot.
4. Returns both snapshots as workflow output.

Use this repository's workflow product path. That means you should use the
`wf` CLI and/or `wf-rpc-server`, create or reuse a workflow deployment, and run
the deployment through the workflow API. Do not solve the challenge with only a
standalone Playwright/Python script.

The repository already includes a deterministic source example at:

```text
examples/browser_click_workflow/
```

You may inspect and use it. A successful final answer must include:

- the commands you ran,
- the deployment id,
- the run id if one was produced,
- evidence that `before.clicked` is `false`,
- evidence that `after.clicked` is `true`,
- whether any server/browser process remains running.

If something fails, report the exact command and error instead of hiding it.
```

- [ ] **Step 3: Create README**

Create `examples/agent_challenges/browser_click_challenge/README.md`:

````markdown
# Opencode Browser Click Challenge Harness

This harness runs agent trials against the browser-click workflow challenge.
It is evidence tooling, not product runtime code.

The deterministic workflow example is:

```text
examples/browser_click_workflow/
```

## One Trial

From the repository root:

```powershell
uv run python examples/agent_challenges/browser_click_challenge/run_opencode_trials.py `
  --model opencode/mimo-v2.5-free `
  --variant high `
  --trials 1
```

Results are written to:

```text
examples/agent_challenges/browser_click_challenge/results/
```

## Optional Playwright MCP Attachment

If you want the agent to have browser-control tools, pass:

```powershell
--attach http://127.0.0.1:4096
```

Start that MCP/tool endpoint separately. For example, one possible MCP server
command is:

```json
{
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest"]
}
```

The baseline challenge does not require Playwright MCP. The score is based on
whether the agent used the workflow product path and produced the expected
workflow output.

## Classification

Each trial is classified as one of:

- `success`: output shows workflow usage and before/after clicked states.
- `workflow_not_used`: output appears to solve the task without `wf`,
  `wf-rpc-server`, deployment, or run evidence.
- `run_failed`: output includes workflow usage but reports a failure.
- `timeout`: the opencode process exceeded the configured timeout.
- `parse_error`: the harness could not read opencode JSON/JSONL output.
- `unknown`: no clear success or failure signal was found.

Committed tests cover harness logic only. They do not invoke opencode.
````

- [ ] **Step 4: Configure result ignores**

Write this content to
`examples/agent_challenges/browser_click_challenge/results/.gitignore`:

```gitignore
*
!.gitignore
```

- [ ] **Step 5: Commit**

Run:

```powershell
git add examples\agent_challenges\browser_click_challenge
git commit -m "docs: add browser click agent challenge prompt"
```

Expected: commit succeeds.

---

## Task 2: Add Harness Core With Tests

**Files:**
- Create: `examples/agent_challenges/browser_click_challenge/run_opencode_trials.py`
- Create: `tests/examples/test_opencode_browser_click_challenge.py`

- [ ] **Step 1: Write failing tests**

Create `tests/examples/test_opencode_browser_click_challenge.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from examples.agent_challenges.browser_click_challenge.run_opencode_trials import (
    TrialConfig,
    build_opencode_command,
    classify_output,
    parse_opencode_output,
    trial_output_path,
)


def test_build_opencode_command_without_attach(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")
    config = TrialConfig(
        model="opencode/mimo-v2.5-free",
        variant="high",
        prompt_path=prompt,
        attach_url=None,
        timeout_seconds=120,
    )

    command = build_opencode_command(config)

    assert command[:2] == ["opencode", "run"]
    assert "--attach" not in command
    assert "--format" in command
    assert "json" in command
    assert "--model" in command
    assert "opencode/mimo-v2.5-free" in command
    assert "hello" in command


def test_build_opencode_command_with_attach(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello", encoding="utf-8")
    config = TrialConfig(
        model="opencode/deepseek-v3.1-free",
        variant="high",
        prompt_path=prompt,
        attach_url="http://127.0.0.1:4096",
        timeout_seconds=120,
    )

    command = build_opencode_command(config)

    assert "--attach" in command
    assert "http://127.0.0.1:4096" in command


def test_parse_opencode_output_reads_json_object() -> None:
    payload = {"text": "wf run start demo.default\nbefore.clicked false\nafter.clicked true"}

    parsed = parse_opencode_output(json.dumps(payload))

    assert parsed["text"] == payload["text"]


def test_parse_opencode_output_reads_last_jsonl_object() -> None:
    payload = "\n".join(
        [
            json.dumps({"type": "log", "text": "starting"}),
            json.dumps({"type": "message", "text": "final"}),
        ]
    )

    parsed = parse_opencode_output(payload)

    assert parsed["text"] == "final"


def test_classify_output_success() -> None:
    result = classify_output(
        """
        uv run wf-rpc-server --config examples/browser_click_workflow/wf.config.json
        uv run wf run start browser_click_case_study.default
        deployment id: browser_click_case_study.default
        run id: run_123
        before.clicked is false
        after.clicked is true
        """
    )

    assert result == "success"


def test_classify_output_workflow_not_used() -> None:
    result = classify_output(
        """
        I wrote a Playwright script.
        before clicked false
        after clicked true
        """
    )

    assert result == "workflow_not_used"


def test_classify_output_run_failed() -> None:
    result = classify_output(
        """
        wf run start browser_click_case_study.default
        error: deployment validation failed
        """
    )

    assert result == "run_failed"


def test_trial_output_path_is_zero_padded(tmp_path: Path) -> None:
    path = trial_output_path(tmp_path, model="opencode/mimo-v2.5-free", index=3)

    assert path.name == "opencode_mimo-v2.5-free-trial-003.json"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/examples/test_opencode_browser_click_challenge.py -q
```

Expected: FAIL because module/functions do not exist.

- [ ] **Step 3: Implement harness module**

Create `examples/agent_challenges/browser_click_challenge/run_opencode_trials.py`:

```python
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


Classification = Literal[
    "success",
    "workflow_not_used",
    "run_failed",
    "timeout",
    "parse_error",
    "unknown",
]

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE_DIR = Path(__file__).resolve().parent
DEFAULT_PROMPT = CHALLENGE_DIR / "prompt.md"
DEFAULT_RESULTS_DIR = CHALLENGE_DIR / "results"


@dataclass(frozen=True, slots=True)
class TrialConfig:
    model: str
    variant: str
    prompt_path: Path
    attach_url: str | None
    timeout_seconds: int


def build_opencode_command(config: TrialConfig) -> list[str]:
    prompt_text = config.prompt_path.read_text(encoding="utf-8")
    command = [
        "opencode",
        "run",
    ]
    if config.attach_url is not None:
        command.extend(["--attach", config.attach_url])
    command.extend(
        [
            prompt_text,
            "--format",
            "json",
            "--model",
            config.model,
            "--variant",
            config.variant,
        ]
    )
    return command


def parse_opencode_output(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError("opencode produced no JSON output")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = _parse_jsonl_tail(text)

    if not isinstance(parsed, dict):
        raise ValueError("opencode output was not a JSON object")
    return parsed


def _parse_jsonl_tail(text: str) -> dict[str, Any]:
    last_error: json.JSONDecodeError | None = None
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed
    if last_error is not None:
        raise last_error
    raise ValueError("opencode output did not contain JSON lines")


def classify_output(text: str) -> Classification:
    lowered = text.lower()
    workflow_markers = [
        "wf ",
        "wf-rpc-server",
        "deployment",
        "run id",
        "run_",
    ]
    used_workflow = any(marker in lowered for marker in workflow_markers)
    failed = any(
        marker in lowered
        for marker in [
            "error:",
            "failed",
            "traceback",
            "exception",
            "validation failed",
        ]
    )
    before_false = (
        "before.clicked is false" in lowered
        or '"before"' in lowered
        and '"clicked": false' in lowered
    )
    after_true = (
        "after.clicked is true" in lowered
        or '"after"' in lowered
        and '"clicked": true' in lowered
    )

    if used_workflow and before_false and after_true and not failed:
        return "success"
    if used_workflow and failed:
        return "run_failed"
    if not used_workflow and (before_false or after_true or "playwright" in lowered):
        return "workflow_not_used"
    return "unknown"


def trial_output_path(results_dir: Path, *, model: str, index: int) -> Path:
    safe_model = model.replace("/", "_").replace(":", "_")
    return results_dir / f"{safe_model}-trial-{index:03d}.json"


def run_trial(config: TrialConfig, *, index: int, results_dir: Path) -> dict[str, Any]:
    command = build_opencode_command(config)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=config.timeout_seconds,
            check=False,
        )
        duration_seconds = time.monotonic() - started
    except subprocess.TimeoutExpired as exc:
        payload = {
            "index": index,
            "config": _jsonable_config(config),
            "command": command,
            "classification": "timeout",
            "duration_seconds": config.timeout_seconds,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "parsed": None,
        }
        _write_trial_result(results_dir, config=config, index=index, payload=payload)
        return payload

    parsed: dict[str, Any] | None
    try:
        parsed = parse_opencode_output(completed.stdout)
        text = _result_text(parsed)
        classification = classify_output(text)
    except Exception:
        parsed = None
        classification = "parse_error"

    payload = {
        "index": index,
        "config": _jsonable_config(config),
        "command": command,
        "classification": classification,
        "duration_seconds": duration_seconds,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "parsed": parsed,
    }
    _write_trial_result(results_dir, config=config, index=index, payload=payload)
    return payload


def _result_text(parsed: dict[str, Any]) -> str:
    for key in ("text", "message", "content", "output"):
        value = parsed.get(key)
        if isinstance(value, str):
            return value
    return json.dumps(parsed, sort_keys=True)


def _jsonable_config(config: TrialConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["prompt_path"] = str(config.prompt_path)
    return payload


def _write_trial_result(
    results_dir: Path,
    *,
    config: TrialConfig,
    index: int,
    payload: dict[str, Any],
) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    path = trial_output_path(results_dir, model=config.model, index=index)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="opencode/mimo-v2.5-free")
    parser.add_argument("--variant", default="high")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--attach", dest="attach_url", default=None)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    args = parser.parse_args(argv)

    if args.trials < 1:
        parser.error("--trials must be >= 1")

    config = TrialConfig(
        model=args.model,
        variant=args.variant,
        prompt_path=args.prompt,
        attach_url=args.attach_url,
        timeout_seconds=args.timeout_seconds,
    )

    summaries: list[dict[str, Any]] = []
    for index in range(1, args.trials + 1):
        result = run_trial(config, index=index, results_dir=args.results_dir)
        summaries.append(
            {
                "index": index,
                "classification": result["classification"],
                "returncode": result["returncode"],
                "duration_seconds": round(float(result["duration_seconds"]), 3),
            }
        )
        print(json.dumps(summaries[-1], sort_keys=True))

    success_count = sum(1 for item in summaries if item["classification"] == "success")
    print(json.dumps({"success_count": success_count, "trial_count": len(summaries)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run:

```powershell
uv run pytest tests/examples/test_opencode_browser_click_challenge.py -q
```

Expected: PASS.

- [ ] **Step 5: Run lint/typecheck**

Run:

```powershell
uv run ruff check examples/agent_challenges/browser_click_challenge/run_opencode_trials.py tests/examples/test_opencode_browser_click_challenge.py
uv run basedpyright --level error examples/agent_challenges/browser_click_challenge/run_opencode_trials.py tests/examples/test_opencode_browser_click_challenge.py
```

Expected: both pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add examples\agent_challenges\browser_click_challenge\run_opencode_trials.py tests\examples\test_opencode_browser_click_challenge.py
git commit -m "test: add opencode browser click challenge harness"
```

Expected: commit succeeds.

---

## Task 3: Add Evidence Docs And Final Verification

**Files:**
- Modify: `docs/add/evidence-index.md`
- Modify: `docs/current_roadmap.md`
- Move: this plan to `docs/historical/superpowers/plans/2026-06-15-opencode-browser-click-challenge-harness.md`

- [ ] **Step 1: Update evidence index**

Add this bullet to `docs/add/evidence-index.md` near the browser-click workflow evidence:

```markdown
- `examples/agent_challenges/browser_click_challenge/`
- `tests/examples/test_opencode_browser_click_challenge.py`
```

- [ ] **Step 2: Update roadmap**

Add this bullet under the product smoke/evidence area in `docs/current_roadmap.md`:

```markdown
- Completed: an opencode browser-click challenge harness captures external
  agent trials against the deterministic browser-click workflow example without
  changing product runtime code.
```

- [ ] **Step 3: Archive plan**

Run:

```powershell
Move-Item -LiteralPath docs\superpowers\plans\2026-06-15-opencode-browser-click-challenge-harness.md -Destination docs\historical\superpowers\plans\2026-06-15-opencode-browser-click-challenge-harness.md
```

Expected: the plan file moves to `docs/historical/superpowers/plans/`.

- [ ] **Step 4: Run final verification**

Run:

```powershell
uv run pytest tests/examples/test_opencode_browser_click_challenge.py tests/docs -q
uv run ruff check examples/agent_challenges/browser_click_challenge tests/examples/test_opencode_browser_click_challenge.py tests/docs
uv run basedpyright --level error examples/agent_challenges/browser_click_challenge tests/examples/test_opencode_browser_click_challenge.py tests/docs
git status --short
```

Expected:
- pytest passes.
- ruff passes.
- basedpyright reports 0 errors.
- `git status --short` shows only intended docs/harness changes before commit.

- [ ] **Step 5: Commit**

Run:

```powershell
git add docs\add\evidence-index.md docs\current_roadmap.md docs\historical\superpowers\plans\2026-06-15-opencode-browser-click-challenge-harness.md
git commit -m "docs: record opencode browser click challenge harness"
```

Expected: commit succeeds.

---

## Manual Trial Command

After implementation, a human can run:

```powershell
uv run python examples/agent_challenges/browser_click_challenge/run_opencode_trials.py `
  --model opencode/mimo-v2.5-free `
  --variant high `
  --trials 1
```

With a Playwright MCP/tool endpoint attached:

```powershell
uv run python examples/agent_challenges/browser_click_challenge/run_opencode_trials.py `
  --model opencode/mimo-v2.5-free `
  --variant high `
  --trials 1 `
  --attach http://127.0.0.1:4096
```

The harness writes detailed JSON files under:

```text
examples/agent_challenges/browser_click_challenge/results/
```

---

## Self-Review Checklist

- The harness does not call opencode during pytest.
- Product runtime code is untouched.
- The prompt requires workflow/deployment/run evidence.
- Classification is deterministic and string-based.
- Trial outputs are gitignored by the local `results/.gitignore`.
- Playwright MCP attachment is optional.
- Docs make clear this is evidence tooling, not product runtime.

# OpenCode Resume Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store OpenCode session metadata first-class in challenge results and expose a safe way to resume incomplete trials with `opencode run --session`.

**Architecture:** Add a focused OpenCode resume helper module that extracts `sessionID` from JSONL stdout, builds continuation prompts from result state, and formats resume commands. The V2 runner records this metadata in every raw result; report projections render it for operators. A small CLI can print the resume command, and optionally execute it into a separate resume result file without mutating original raw evidence.

**Tech Stack:** Python 3.14, stdlib `json`/`subprocess`/`argparse`, existing `examples.agent_challenges` harness, pytest, Pydantic report DTOs.

---

## File Structure

- Create `examples/agent_challenges/opencode_resume.py`
  - Owns `extract_session_id`, prompt selection, command construction, and resume-result path selection.
  - No challenge-specific assertions here.
- Modify `examples/agent_challenges/runner.py`
  - Stores `opencode` metadata in the raw result after stdout/stderr are known.
  - Does not change task classification rules.
- Modify `examples/agent_challenges/report_models.py`
  - Adds strict DTOs for bounded OpenCode metadata in machine reports.
- Modify `examples/agent_challenges/reports.py`
  - Renders resume metadata and command in `final-report.md` / `*.report.md`.
- Create `examples/agent_challenges/resume_trial.py`
  - CLI for printing or executing a resume from one raw result JSON.
- Modify `tests/examples/test_agent_challenge_harness_v2.py`
  - Runner-level coverage for storing metadata.
- Modify `tests/examples/test_agent_challenge_reports.py`
  - Report rendering and machine projection coverage.
- Create `tests/examples/test_agent_challenge_resume.py`
  - Unit tests for session extraction, prompt selection, command construction, and CLI behavior.
- Modify `docs/runbooks/agent-challenge-evaluation.md`
  - Adds operator instructions for incomplete/timeouts and resume.
- Modify `docs/current_roadmap.md`
  - Records completion when implementation is done.

---

### Task 1: Add OpenCode Resume Helper

**Files:**
- Create: `examples/agent_challenges/opencode_resume.py`
- Test: `tests/examples/test_agent_challenge_resume.py`

- [ ] **Step 1: Write failing tests for session extraction and prompt selection**

Create `tests/examples/test_agent_challenge_resume.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from examples.agent_challenges.opencode_resume import (
    build_resume_command,
    extract_session_id,
    resume_prompt_for_result,
    resume_result_path,
)


def _event(**payload: object) -> str:
    return json.dumps(payload, separators=(",", ":"))


def test_extract_session_id_reads_top_level_session_id() -> None:
    stdout = "\n".join(
        [
            _event(type="step_start", sessionID="ses_abc"),
            _event(type="text", sessionID="ses_def", text="later"),
        ]
    )

    assert extract_session_id(stdout) == "ses_abc"


def test_extract_session_id_reads_nested_part_session_id() -> None:
    stdout = _event(type="step_start", part={"sessionID": "ses_nested"})

    assert extract_session_id(stdout) == "ses_nested"


def test_extract_session_id_returns_none_for_empty_or_malformed_stdout() -> None:
    assert extract_session_id("") is None
    assert extract_session_id("not json\n{}") is None


def test_resume_prompt_asks_continue_for_timeout_with_partial_stdout() -> None:
    prompt = resume_prompt_for_result(
        {
            "task_outcome": "timeout",
            "stdout": _event(type="step_start", sessionID="ses_abc"),
        }
    )

    assert "continue" in prompt.lower()
    assert "do not restart" in prompt.lower()


def test_resume_prompt_asks_for_final_report_when_work_is_done_but_report_missing() -> None:
    prompt = resume_prompt_for_result(
        {
            "task_outcome": "failed",
            "assertion_failures": [
                "could not extract challenge report for required_fields evaluation"
            ],
            "stdout": _event(type="text", sessionID="ses_abc", text="run completed"),
        }
    )

    assert "do not continue coding" in prompt.lower()
    assert "challenge_report" in prompt


def test_build_resume_command_includes_attach_session_model_variant_and_prompt() -> None:
    command = build_resume_command(
        session_id="ses_abc",
        attach_url="http://127.0.0.1:8192/",
        model="opencode/deepseek-v4-flash-free",
        variant="max",
        prompt="continue?",
    )

    assert command == [
        "opencode",
        "run",
        "--session",
        "ses_abc",
        "--attach",
        "http://127.0.0.1:8192/",
        "--format",
        "json",
        "--model",
        "opencode/deepseek-v4-flash-free",
        "--variant",
        "max",
        "continue?",
    ]


def test_resume_result_path_uses_next_resume_index(tmp_path: Path) -> None:
    original = tmp_path / "trial.json"
    original.write_text("{}", encoding="utf-8")
    (tmp_path / "trial.resume-001.json").write_text("{}", encoding="utf-8")

    assert resume_result_path(original).name == "trial.resume-002.json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/examples/test_agent_challenge_resume.py -q
```

Expected: fails because `examples.agent_challenges.opencode_resume` does not exist.

- [ ] **Step 3: Implement the helper module**

Create `examples/agent_challenges/opencode_resume.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FINAL_REPORT_PROMPT = (
    "Your workflow attempt is over. Do not continue coding. Return only the "
    "final challenge report using the required challenge_report YAML schema. "
    "Include run_id, evidence, failed attempts, read flags, missed requirements, "
    "and whether the run succeeded."
)

CONTINUE_PROMPT = (
    "Continue this same trial from the current session. Do not restart in a new "
    "workspace. If the workflow is already complete, stop and return only the "
    "final challenge_report YAML using the required schema."
)


def _event_session_id(event: dict[str, Any]) -> str | None:
    session_id = event.get("sessionID")
    if isinstance(session_id, str) and session_id:
        return session_id
    part = event.get("part")
    if isinstance(part, dict):
        nested = part.get("sessionID")
        if isinstance(nested, str) and nested:
            return nested
    return None


def extract_session_id(stdout: str) -> str | None:
    """Return the first OpenCode session id found in JSONL stdout."""
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        session_id = _event_session_id(event)
        if session_id is not None:
            return session_id
    return None


def resume_prompt_for_result(result: dict[str, object]) -> str:
    """Choose a continuation prompt from the result failure shape."""
    task_outcome = result.get("task_outcome")
    assertion_failures = result.get("assertion_failures")
    failures = assertion_failures if isinstance(assertion_failures, list) else []
    if task_outcome == "timeout":
        return CONTINUE_PROMPT
    if any("could not extract challenge report" in str(item) for item in failures):
        return FINAL_REPORT_PROMPT
    if result.get("parsed") is None and result.get("stdout"):
        return FINAL_REPORT_PROMPT
    return CONTINUE_PROMPT


def build_resume_command(
    *,
    session_id: str,
    attach_url: str | None,
    model: str,
    variant: str,
    prompt: str,
) -> list[str]:
    command = ["opencode", "run", "--session", session_id]
    if attach_url is not None:
        command.extend(["--attach", attach_url])
    command.extend(["--format", "json", "--model", model, "--variant", variant, prompt])
    return command


def resume_result_path(result_path: Path) -> Path:
    stem = result_path.with_suffix("")
    index = 1
    while True:
        candidate = stem.with_name(f"{stem.name}.resume-{index:03d}.json")
        if not candidate.exists():
            return candidate
        index += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/examples/test_agent_challenge_resume.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add examples/agent_challenges/opencode_resume.py tests/examples/test_agent_challenge_resume.py
git commit -m "feat: add opencode resume helpers"
```

---

### Task 2: Store Resume Metadata In Raw V2 Results

**Files:**
- Modify: `examples/agent_challenges/runner.py`
- Test: `tests/examples/test_agent_challenge_harness_v2.py`

- [ ] **Step 1: Add failing runner tests**

Append to `tests/examples/test_agent_challenge_harness_v2.py`:

```python
def test_v2_runner_stores_opencode_resume_metadata(tmp_path: Path) -> None:
    from subprocess import CompletedProcess

    from examples.agent_challenges.models import InstructionProfile
    from examples.agent_challenges.runner import run_v2_trial

    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))
    stdout = (
        '{"type":"step_start","sessionID":"ses_runner"}\n'
        '{"type":"text","sessionID":"ses_runner","text":"```yaml\\n'
        'challenge_report:\\n'
        '  used_product_path: true\\n'
        '  used_helper_script: false\\n'
        '  before_clicked: false\\n'
        '  after_clicked: true\\n'
        '  run_failed: false\\n'
        '  leftover_processes: false\\n'
        '```"}\n'
    )

    def fake_run(*args: object, **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(args=args, returncode=0, stdout=stdout, stderr="")

    result = run_v2_trial(
        challenge,
        profile=InstructionProfile.NONE,
        model="opencode/deepseek-v4-flash-free",
        variant="max",
        index=1,
        results_dir=tmp_path / "results",
        workspaces_dir=tmp_path / "workspaces",
        attach_url="http://127.0.0.1:8192/",
        run_fn=fake_run,
    )

    opencode = result["opencode"]
    assert opencode["session_id"] == "ses_runner"
    assert opencode["attach_url"] == "http://127.0.0.1:8192/"
    assert opencode["model"] == "opencode/deepseek-v4-flash-free"
    assert opencode["variant"] == "max"
    assert opencode["resume_command"][0:4] == [
        "opencode",
        "run",
        "--session",
        "ses_runner",
    ]
    assert "challenge_report" in opencode["resume_prompt"]


def test_v2_runner_stores_null_session_when_stdout_has_no_session(tmp_path: Path) -> None:
    from subprocess import CompletedProcess

    from examples.agent_challenges.models import InstructionProfile
    from examples.agent_challenges.runner import run_v2_trial

    challenge = load_challenge_manifest(_write_manifest(tmp_path / "challenge"))

    def fake_run(*args: object, **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(args=args, returncode=1, stdout="", stderr="boom")

    result = run_v2_trial(
        challenge,
        profile=InstructionProfile.NONE,
        model="opencode/deepseek-v4-flash-free",
        variant="max",
        index=1,
        results_dir=tmp_path / "results",
        workspaces_dir=tmp_path / "workspaces",
        run_fn=fake_run,
    )

    opencode = result["opencode"]
    assert opencode["session_id"] is None
    assert opencode["resume_command"] is None
```

These tests use the existing `_write_manifest` helper and the already-imported
`load_challenge_manifest` function at the top of the file. Do not invent a
second fixture.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/examples/test_agent_challenge_harness_v2.py::test_v2_runner_stores_opencode_resume_metadata tests/examples/test_agent_challenge_harness_v2.py::test_v2_runner_stores_null_session_when_stdout_has_no_session -q
```

Expected: fails because `result["opencode"]` is missing.

- [ ] **Step 3: Store metadata in `run_v2_trial`**

In `examples/agent_challenges/runner.py`, import helpers near the other challenge harness imports:

```python
from examples.agent_challenges.opencode_resume import (
    build_resume_command,
    extract_session_id,
    resume_prompt_for_result,
)
```

After `report_paths` is defined and before `result` is built, add:

```python
    opencode_session_id = extract_session_id(stdout)
```

After `result` is built, before optional `assertion_failures` are attached, add:

```python
    resume_prompt = resume_prompt_for_result(result)
    result["opencode"] = {
        "attach_url": attach_url,
        "command": command,
        "model": model,
        "variant": variant,
        "session_id": opencode_session_id,
        "resume_prompt": resume_prompt,
        "resume_command": (
            build_resume_command(
                session_id=opencode_session_id,
                attach_url=attach_url,
                model=model,
                variant=variant,
                prompt=resume_prompt,
            )
            if opencode_session_id is not None
            else None
        ),
    }
```

Keep `model` and `variant` at top-level too; this is additive metadata for operators.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/examples/test_agent_challenge_harness_v2.py::test_v2_runner_stores_opencode_resume_metadata tests/examples/test_agent_challenge_harness_v2.py::test_v2_runner_stores_null_session_when_stdout_has_no_session -q
```

Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add examples/agent_challenges/runner.py tests/examples/test_agent_challenge_harness_v2.py
git commit -m "feat: store opencode resume metadata"
```

---

### Task 3: Render Resume Metadata In Reports

**Files:**
- Modify: `examples/agent_challenges/report_models.py`
- Modify: `examples/agent_challenges/reports.py`
- Test: `tests/examples/test_agent_challenge_reports.py`

- [ ] **Step 1: Write failing report projection test**

Append to `tests/examples/test_agent_challenge_reports.py`:

```python
def test_trial_report_renders_opencode_resume_metadata(tmp_path: Path) -> None:
    from examples.agent_challenges.report_models import build_trial_report
    from examples.agent_challenges.reports import render_trial_report_markdown

    result = _raw_result(tmp_path)
    result["opencode"] = {
        "attach_url": "http://127.0.0.1:8192/",
        "command": ["opencode", "run", "--format", "json", "prompt"],
        "model": "opencode/deepseek-v4-flash-free",
        "variant": "max",
        "session_id": "ses_report",
        "resume_prompt": "continue?",
        "resume_command": [
            "opencode",
            "run",
            "--session",
            "ses_report",
            "--attach",
            "http://127.0.0.1:8192/",
            "--format",
            "json",
            "--model",
            "opencode/deepseek-v4-flash-free",
            "--variant",
            "max",
            "continue?",
        ],
    }

    report = build_trial_report(result, audit=None)
    rendered = render_trial_report_markdown(report)
    machine = report.model_dump(mode="json")

    assert machine["opencode"]["session_id"] == "ses_report"
    assert "## OpenCode Resume" in rendered
    assert "ses_report" in rendered
    assert "opencode run --session ses_report" in rendered
```

Use the existing `_raw_result` helper in the file. Do not create duplicate
minimal result setup.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/examples/test_agent_challenge_reports.py::test_trial_report_renders_opencode_resume_metadata -q
```

Expected: fails because `TrialReport` forbids extra `opencode`.

- [ ] **Step 3: Add report DTOs**

In `examples/agent_challenges/report_models.py`, add after `TrialIdentity`:

```python
class OpenCodeRunMetadata(StrictReportModel):
    attach_url: str | None = None
    command: list[str] = Field(default_factory=list)
    model: str = ""
    variant: str = ""
    session_id: str | None = None
    resume_prompt: str = ""
    resume_command: list[str] | None = None
```

Add field to `TrialReport`:

```python
    opencode: OpenCodeRunMetadata | None = None
```

Add helper:

```python
def _build_opencode_metadata(result: dict[str, object]) -> OpenCodeRunMetadata | None:
    raw = result.get("opencode")
    if not isinstance(raw, dict):
        return None
    resume_command = raw.get("resume_command")
    return OpenCodeRunMetadata(
        attach_url=_str_none(raw.get("attach_url")),
        command=_list_str(raw.get("command")),
        model=_str(raw.get("model")),
        variant=_str(raw.get("variant")),
        session_id=_str_none(raw.get("session_id")),
        resume_prompt=_str(raw.get("resume_prompt")),
        resume_command=_list_str(resume_command)
        if isinstance(resume_command, list)
        else None,
    )
```

In `_build_trial_report`, pass:

```python
        opencode=_build_opencode_metadata(result),
```

- [ ] **Step 4: Render markdown section**

In `examples/agent_challenges/reports.py`, add a helper near other render helpers:

```python
def _shell_join(command: list[str]) -> str:
    return " ".join(command)
```

Then in `render_trial_report_markdown`, after the Outcome section and before Agent Self-Report, add:

```python
    if report.opencode is not None:
        lines.append("## OpenCode Resume")
        lines.append("")
        if report.opencode.session_id:
            lines.append(f"- Session: `{report.opencode.session_id}`")
        else:
            lines.append("- Session: not captured")
        if report.opencode.attach_url:
            lines.append(f"- Attach URL: `{report.opencode.attach_url}`")
        if report.opencode.resume_command:
            lines.append("")
            lines.append("```powershell")
            lines.append(_shell_join(report.opencode.resume_command))
            lines.append("```")
        if report.opencode.resume_prompt:
            lines.append("")
            lines.append("Resume prompt:")
            lines.append("")
            lines.append("```text")
            lines.append(report.opencode.resume_prompt)
            lines.append("```")
        lines.append("")
```

This uses simple shell rendering for readability. The authoritative machine form remains the JSON list in `*.report.json`.

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
uv run pytest tests/examples/test_agent_challenge_reports.py::test_trial_report_renders_opencode_resume_metadata -q
```

Expected: passes.

- [ ] **Step 6: Commit**

```bash
git add examples/agent_challenges/report_models.py examples/agent_challenges/reports.py tests/examples/test_agent_challenge_reports.py
git commit -m "feat: show opencode resume metadata in reports"
```

---

### Task 4: Add `resume_trial.py` CLI

**Files:**
- Create: `examples/agent_challenges/resume_trial.py`
- Test: `tests/examples/test_agent_challenge_resume.py`
- Modify: `docs/runbooks/agent-challenge-evaluation.md`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/examples/test_agent_challenge_resume.py`:

```python
def test_resume_trial_prints_resume_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from examples.agent_challenges.resume_trial import main

    result_path = tmp_path / "trial.json"
    result_path.write_text(
        json.dumps(
            {
                "model": "opencode/deepseek-v4-flash-free",
                "variant": "max",
                "opencode": {
                    "attach_url": "http://127.0.0.1:8192/",
                    "session_id": "ses_cli",
                    "resume_prompt": "continue?",
                    "resume_command": [
                        "opencode",
                        "run",
                        "--session",
                        "ses_cli",
                        "--attach",
                        "http://127.0.0.1:8192/",
                        "--format",
                        "json",
                        "--model",
                        "opencode/deepseek-v4-flash-free",
                        "--variant",
                        "max",
                        "continue?",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    assert main(["--from-result", str(result_path), "--print-command"]) == 0
    output = capsys.readouterr().out
    assert "opencode run --session ses_cli" in output


def test_resume_trial_run_writes_resume_result(tmp_path: Path) -> None:
    from subprocess import CompletedProcess

    from examples.agent_challenges.resume_trial import resume_from_result

    result_path = tmp_path / "trial.json"
    result_path.write_text(
        json.dumps(
            {
                "model": "opencode/deepseek-v4-flash-free",
                "variant": "max",
                "opencode": {
                    "attach_url": None,
                    "session_id": "ses_cli",
                    "resume_prompt": "continue?",
                    "resume_command": [
                        "opencode",
                        "run",
                        "--session",
                        "ses_cli",
                        "--format",
                        "json",
                        "--model",
                        "opencode/deepseek-v4-flash-free",
                        "--variant",
                        "max",
                        "continue?",
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        calls.append(command)
        return CompletedProcess(command, 0, stdout='{"type":"text","text":"done"}\n', stderr="")

    output_path = resume_from_result(result_path, run_fn=fake_run)

    assert output_path.name == "trial.resume-001.json"
    assert calls[0][0:4] == ["opencode", "run", "--session", "ses_cli"]
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["source_result_path"] == str(result_path.resolve())
    assert payload["stdout"].strip()
```

Add `import pytest` at the top of the file if missing.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/examples/test_agent_challenge_resume.py::test_resume_trial_prints_resume_command tests/examples/test_agent_challenge_resume.py::test_resume_trial_run_writes_resume_result -q
```

Expected: fails because `resume_trial.py` does not exist.

- [ ] **Step 3: Implement CLI**

Create `examples/agent_challenges/resume_trial.py`:

```python
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    from .opencode_resume import resume_result_path
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from examples.agent_challenges.opencode_resume import resume_result_path


RunFn = Callable[..., subprocess.CompletedProcess[str]]


def _load_command(result: dict[str, Any]) -> list[str]:
    opencode = result.get("opencode")
    if not isinstance(opencode, dict):
        raise ValueError("result has no opencode metadata")
    command = opencode.get("resume_command")
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        raise ValueError("result has no resume_command; session id may be missing")
    return command


def _display_command(command: list[str]) -> str:
    return " ".join(command)


def resume_from_result(
    result_path: Path,
    *,
    run_fn: RunFn = subprocess.run,
) -> Path:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("result file must contain a JSON object")
    command = _load_command(result)
    started = time.monotonic()
    completed = run_fn(
        command,
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    payload = {
        "harness_version": "v2-resume",
        "source_result_path": str(result_path.resolve()),
        "command": command,
        "duration_seconds": round(time.monotonic() - started, 3),
        "returncode": completed.returncode,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }
    output_path = resume_result_path(result_path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print or run an OpenCode trial resume command.")
    parser.add_argument("--from-result", type=Path, required=True)
    parser.add_argument("--print-command", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = json.loads(args.from_result.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError("result file must contain a JSON object")
        command = _load_command(result)
        if args.run:
            print(resume_from_result(args.from_result).as_posix())
        else:
            print(_display_command(command))
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Default behavior prints the command; `--print-command` is accepted for clarity but not required. Execution writes a sidecar `.resume-NNN.json`; it never overwrites the original result.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/examples/test_agent_challenge_resume.py -q
```

Expected: all resume tests pass.

- [ ] **Step 5: Update runbook**

In `docs/runbooks/agent-challenge-evaluation.md`, add after “Save A Manual Audit”:

```md
## Resume An Incomplete OpenCode Trial

When a result captures an OpenCode `sessionID`, the report includes an
`OpenCode Resume` section. Print the resume command with:

```powershell
uv run python examples/agent_challenges/resume_trial.py `
  --from-result examples/agent_challenges/browser_click_challenge/results/opencode_deepseek-v4-flash-free-trial-034.json
```

Run the resume and save a sidecar result with:

```powershell
uv run python examples/agent_challenges/resume_trial.py `
  --from-result examples/agent_challenges/browser_click_challenge/results/opencode_deepseek-v4-flash-free-trial-034.json `
  --run
```

The resume command writes `*.resume-001.json` beside the original result and
does not mutate the original raw result. Use manual audit to decide whether the
resumed output completes the trial or only provides additional evidence.
```

- [ ] **Step 6: Commit**

```bash
git add examples/agent_challenges/resume_trial.py tests/examples/test_agent_challenge_resume.py docs/runbooks/agent-challenge-evaluation.md
git commit -m "feat: add opencode trial resume cli"
```

---

### Task 5: Final Verification And Roadmap

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-06-30-opencode-resume-metadata.md` to `docs/historical/superpowers/plans/2026-06-30-opencode-resume-metadata.md`

- [ ] **Step 1: Update roadmap**

Add under the active agent evaluation area in `docs/current_roadmap.md`:

```md
- Completed: agent challenge results now record OpenCode session metadata and
  resume commands, so incomplete provider runs can be continued without
  mutating original raw evidence.
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest tests/examples/test_agent_challenge_resume.py tests/examples/test_agent_challenge_harness_v2.py tests/examples/test_agent_challenge_reports.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run lint and typecheck**

Run:

```bash
uv run ruff check examples/agent_challenges tests/examples
uv run ruff format --check examples/agent_challenges tests/examples
uv run basedpyright --level error examples/agent_challenges tests/examples
```

Expected: ruff clean, format clean, basedpyright 0 errors.

- [ ] **Step 4: Smoke print against a real result**

Run:

```bash
uv run python examples/agent_challenges/resume_trial.py --from-result examples/agent_challenges/browser_click_challenge/results/opencode_deepseek-v4-flash-free-trial-034.json
```

Expected: prints an `opencode run --session ...` command if that result still exists and contains a session id. If the result was cleaned up locally, use any current V2 result that has `opencode.session_id`.

- [ ] **Step 5: Archive this plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-30-opencode-resume-metadata.md docs/historical/superpowers/plans/2026-06-30-opencode-resume-metadata.md
```

- [ ] **Step 6: Commit**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-06-30-opencode-resume-metadata.md
git commit -m "docs: record opencode resume metadata support"
```

---

## Self-Review

- Spec coverage: The plan stores `attach_url`, `opencode_session_id`, exact command, resume prompt, and resume command. It handles “continue” versus “final report only” prompt selection from result state. It adds report visibility and a CLI for printing/running resume commands.
- Placeholder scan: No TODO/TBD placeholders remain. Each code-changing step includes concrete code and commands.
- Type consistency: The raw result key is `opencode`, with `session_id`, `attach_url`, `command`, `model`, `variant`, `resume_prompt`, and `resume_command`. The report DTO uses the same names. The CLI reads the same `opencode.resume_command`.

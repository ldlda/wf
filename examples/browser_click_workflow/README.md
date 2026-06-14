# Browser Click Workflow Example

This example demonstrates a serial multi-node workflow over a trusted Python
source:

```text
open_click_page -> wait_for_click -> collect_snapshots
```

It opens a local HTML page with one visible button, captures a bounded JSON
snapshot before the click, performs a deterministic simulated click by default,
captures an after snapshot, closes the local server, and returns both snapshots
as workflow output.

The example deliberately avoids browser screenshots and base64 payloads. The
snapshots are small JSON objects suitable for CLI and LLM-agent output.

## Run

From the repository root:

```powershell
uv run wf config validate examples/browser_click_workflow/wf.config.json
uv run wf-rpc-server --config examples/browser_click_workflow/wf.config.json
```

In another terminal:

```powershell
uv run wf --config examples/browser_click_workflow/wf.config.json status
uv run wf --config examples/browser_click_workflow/wf.config.json cap list --source local.browser_click
```

The full artifact/deployment/run lifecycle is covered by:

```powershell
uv run pytest tests/examples/test_browser_click_workflow_example.py -q
```

## Manual Browser Mode

The checked-in test uses `"simulate": true` and `"open_browser": false`.
For manual experimentation, set `"open_browser": true` in the run input and
use `"simulate": false`; then click the button before `timeout_seconds` elapses.
Any browser or local server opened by the source is closed by the final
`collect_snapshots` node.
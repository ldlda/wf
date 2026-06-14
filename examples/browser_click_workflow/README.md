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
uv run wf --config examples/browser_click_workflow/wf.config.json --local status
```

List the configured Python source capabilities:

```powershell
uv run wf --config examples/browser_click_workflow/wf.config.json cap list --source local.browser_click
```

## Draft Patch Lifecycle

This example includes `draft-patch.json`, an RFC 6902 JSON Patch array that
turns a single-capability draft into the three-node workflow:

```text
open_click_page -> wait_for_click -> collect_snapshots
```

Apply and run it through the product-facing CLI:

```powershell
uv run wf --config examples/browser_click_workflow/wf.config.json draft create-from-capability browser_click_ws local.browser_click.open_click_page --name browser_click_workflow
uv run wf --config examples/browser_click_workflow/wf.config.json draft patch browser_click_ws --revision 1 --input-file examples/browser_click_workflow/draft-patch.json
uv run wf --config examples/browser_click_workflow/wf.config.json draft validate browser_click_ws
uv run wf --config examples/browser_click_workflow/wf.config.json draft save browser_click_ws --artifact browser_click_case_study --version 1 --title "Browser Click Case Study" --outcome ok
uv run wf --config examples/browser_click_workflow/wf.config.json deploy save browser_click_case_study.default --artifact browser_click_case_study --version 1 --binding local.browser_click=local.browser_click
uv run wf --config examples/browser_click_workflow/wf.config.json deploy validate browser_click_case_study.default
uv run wf --config examples/browser_click_workflow/wf.config.json run start browser_click_case_study.default --input-file examples/browser_click_workflow/run-input.json
```

The example config has a local client target, so these commands build the
configured workflow server in-process. Use `wf-rpc-server --config
examples/browser_click_workflow/wf.config.json` plus `wf --url ...` only when
you specifically want to exercise the JSON-RPC server path.

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

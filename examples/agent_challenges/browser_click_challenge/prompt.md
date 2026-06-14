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

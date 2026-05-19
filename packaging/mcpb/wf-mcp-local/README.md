# wf-mcp Local MCPB

This is a local-development Claude Desktop bundle for `wf-mcp`.

It is intentionally not self-contained. The manifest runs:

```text
uv run --directory C:/Users/Admin/Documents/lda.chat/lda-workflow-as-struct wf-mcp --config C:/Users/Admin/Documents/lda.chat/lda-workflow-as-struct/wf_mcp.config.json serve --transport stdio --resources-as-tools --prompts-as-tools --search-tools --safe-tool-names
```

Important behavior:

- `--config` points to the broker config file.
- `store_root` is read from that config file.
- `wf.admin.reload_config` reloads the same config file, so changing
  `store_root` should happen in the config, not in a separate CLI override.
- Upstream stdio tools can set their own working directory with connection
  metadata field `cwd`.
- `--resources-as-tools` and `--prompts-as-tools` are enabled because some
  MCPB/Claude paths expose tools more reliably than native resources/prompts.
- `--safe-tool-names` maps runtime MCP tool ids to Claude-safe names such as
  `wf_workflow_list_capabilities` while payload values keep dotted names.

This package assumes `uv` is available on `PATH`.

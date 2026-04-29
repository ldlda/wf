# Suggested Commands

Use PowerShell on Windows from the repo root.

Testing:
- `uv run --with pytest pytest -q`
- Focused example: `uv run --with pytest pytest tests/test_wf_mcp_transparent_proxy.py -q`

Lint/type checks:
- `uv run ruff check src/wf_mcp tests`
- Focused basedpyright example: `uv run basedpyright src/wf_mcp/transparent_proxy.py --level error`

Formatting:
- `uv run ruff format`

CLI / MCP server:
- `uv run wf-mcp --config wf_mcp.config.json serve`
- Transparent proxy mode is default.
- Old broker mode: `uv run wf-mcp --config wf_mcp.config.json serve --mode broker`
- Optional compatibility/search flags: `--resources-as-tools`, `--prompts-as-tools`, `--search-tools`

Useful Windows shell commands:
- Fast search: `rg "pattern" path`
- List files: `Get-ChildItem -Force`
- Read file: `Get-Content -Path path`
- Git status: `git status --short`
- Diff: `git diff -- path`
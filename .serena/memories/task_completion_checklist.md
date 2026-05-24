# Task Completion Checklist

Before considering a code task done:

- Run focused tests for the touched area.
- Run full tests when the change affects shared behavior: `uv run --with pytest pytest -q`.
- Run ruff on touched source/tests, usually `uv run ruff check src/wf_mcp tests` for MCP work.
- Run focused basedpyright at error level for new or heavily changed files when type issues are likely.
- Check `git status --short` and distinguish user-owned config changes from code changes.
- For MCP/proxy changes, consider direct FastMCP client verification when Codex's native MCP tool registry is stale.
- Summarize functional changes and verification results concisely.

Recent known-good full-suite count after proxy tool pagination/detail work:

- `48 passed, 1 skipped`

Known environment notes:

- Windows sandbox may block commands with `CreateProcessAsUserW failed: 5`; retry important commands with escalation rather than working around via unsafe shell tricks.
- Codex/native MCP tool schemas may not refresh dynamically after `wf-mcp` hot reload. A fresh client/session may be needed to see newly added MCP tools.

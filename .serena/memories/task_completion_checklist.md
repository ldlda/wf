# Task Completion Checklist

Before considering a code task done:
- Run focused tests for the touched area.
- Run full tests when the change affects shared behavior: `uv run --with pytest pytest -q`.
- Run ruff on touched source/tests, usually `uv run ruff check src/wf_mcp tests` for MCP work.
- Run focused basedpyright at error level for new or heavily changed files when type issues are likely.
- Check `git status --short` and distinguish user-owned config changes from code changes.
- Summarize functional changes and verification results concisely.

Known environment note:
- Windows sandbox may block commands with `CreateProcessAsUserW failed: 5`; retry important commands with escalation rather than working around via unsafe shell tricks.
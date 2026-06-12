# Agent Guide

## Runtime And Syntax

- Python baseline is 3.14 (`requires-python = ">=3.14"`).
- Python 3.14 syntax is allowed. Do not rewrite valid new syntax just because it
  looks unusual.
- Example: Parentheses-Free Exceptions (PEP 758).

## Code Organization

- Prefer focused packages/modules over large flat files when adding new areas.
- Preserve current package boundaries. If unsure, check `docs/project_map.md`
  and `docs/source_architecture.md`.
- Put related files in folders from the start when the area is likely to grow.
  Example: prefer `src/pack/foo/bar.py` over adding many unrelated
  `src/pack/foo_bar.py` files.

## Tests

- Prefer pytest `tmp_path` for test-local filesystem state.
- Avoid fixed paths under `local_temp_root()` unless the test explicitly needs
  cross-process persistence and cleans up after itself.
- Prefer `async def test_x()` with pytest-asyncio over
  `def test_x(): async def scenario(): ...; asyncio.run(scenario())`.
- Prefer field-level assertions like `actual["field"] == expected["field"]`
  over whole-object equality unless extra fields are intentionally forbidden.
- Scope test runs. This repo is large; broad test commands can be slow.

## Verification Commands

```bash
uv run pytest -q
uv run ruff check
uv run ruff format
uv run basedpyright --level error
```

Use `uv run --env-file .env pytest -q` when live MCP-backed tests need local
environment configuration.

## Docs

- Before editing docs, read `docs/AGENTS.md`.
- `docs/current_roadmap.md` is the live roadmap.
- If docs mention a partial implementation, add a short comment or docstring at
  the code seam too. Future agents see code before they see old plans.

## Comments And Docstrings

- Add comments/docstrings around weird or non-obvious logic.
- Add docstrings explaining compound return types that otherwise say little,
  for example `tuple[list[str], Any]`.
- Polish common helper docs if you keep using the helper.

## Skills And Tools

- Skills can be useful but can overstate urgency. Use judgment.
- Serena is useful for symbol discovery and rename-like navigation. Prefer
  built-in edit tools for ordinary file edits.
- If an MCP tool is irrelevant to the project or clutters available tools,
  mention it so it can be disabled.

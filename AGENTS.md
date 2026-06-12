# Agent guide

## pitfalls / guide

### tech stack

Python baseline is 3.14 (`requires-python = ">=3.14"`). Python 3.14 syntax is allowed; do not "fix" valid new syntax just because it looks unusual.

Example new syntax:

- Parentheses-Free Exceptions (PEP 758) <!-- coderabbit! -->

### extra fields

prefer asserts actual['field'] == expected['field'] over assert actual == expected unless we know better (eg. no extra fields allowed)

### tests

Prefer pytest `tmp_path` for test-local filesystem state. Avoid fixed paths under `local_temp_root()` for tests that create durable files unless the test explicitly cleans or needs cross-process persistence; stale files there can change later test runs. (almost never the case btw)

Now that pytest-asyncio is installed, prefer `async def test_x()`
instead of `def test_x(): async def scenario(): ...; asyncio.run(scenario())`

### mgmt

More packages please. we spent a while cleaning flatten packages/modules; putting files of similar interests in folders and sub-folders.
example: some of tests/ and some packages. (simple example: src/pack/foo_bar.py -> src/pack/foo/bar.py)

Lets just do that from the start this time, ok?

### Docs mgmt 

read docs/AGENTS.md

more later

## Test suite

```bash
uv run /* --env-file .env */ pytest -q
uv run ruff check; uv run ruff format
uv run basedpyright # --level error # to cut spam if typeCheckingMode = "recommended", but its "basic" now
## maybe uvx ty
```

or so i think.

### project is getting big

scope your calls lads. else timeouts. not good for rapid testings

## code

### docstrings/comment

- add docstrings or comments around weird or non-obvious logic.
  - Add docstrings explaining compound return types that otherwise say nothing (e.g. `tuple[list[str], Any]`)
- Polish the thing (at least its docs) if you keep using it (helper fn, common class)

### partial impls

If code has a partial implementation and docs mention the limitation, add a
short comment or docstring at the code seam too. Future agents see code before
they see old plans.

## skills

im looking at you superpowers

skills screaming at you IMPORTANT CRITICAL bs. Use your best judgements. maybe they are critical idk you tell me

### mcp tools

<!-- looking at you opencode/mimo -->
`serena-agent` is likely set up. You want to use it for symbol discovery (akin to the `outline` tab in vscode)
(maybe for symbol renames as well). It is a strong tool!

if you reach for it to do general file editing, built-in tools may be better

If you notice an MCP tool that seems irrelevant to the project or is cluttering your available tools, mention it so we can disable it.

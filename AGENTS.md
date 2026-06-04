# pitfalls

prefer asserts actual['field'] == expected['field'] over assert actual == expected unless we know better (eg. no extra fields allowed)

Prefer pytest `tmp_path` for test-local filesystem state. Avoid fixed paths under `local_temp_root()` for tests that create durable files unless the test explicitly cleans or needs cross-process persistence; stale files there can change later test runs.

more later

# Test suite

```bash
uv run /* --env-file .env */ pytest -q
(uvx / uv run) ruff check / format
uv run basedpyright --level error # error to cut spam
# maybe uvx ty
```

or so i think.

## project is getting big

scope your calls lads. else timeouts. not good for rapid testings

# partial impls

if a capability is partial until something else frees, or whatever else of the same kind, and you note it in docs,
you also put a short comment/docstrings at the site to state the problem, and may also refer to the docs there.

<!-- should this be global? putting docstrings/comment is global -->

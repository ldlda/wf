# pitfalls

prefer asserts actual['field'] == expected['field'] over assert actual == expected unless we know better (eg. no extra fields allowed)

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

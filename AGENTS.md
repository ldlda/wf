# pitfalls

prefer asserts dict['field'] == dict['field'] over assert dict == dict unless we know better (eg. no extra fields allowed)

more later

# Test suite

```bash
uv run /* --env-file .env */ pytest -q
(uvx / uv run) ruff check / format
uv run basedpyright --level error # error to cut spam
# maybe uvx ty
```

or so i think.

<!-- if this file comes with every request, tell me, and you have perms to cut the files down. goo goo ga ga. use caveman skill (only) for repeated artifacts. -->

# partial impls

if a capability is partial until something else frees, or whatever else of the same kind, and you note it in docs,
you also put a short comment/docstrings at the site to state the problem, and may also refer to the docs there.

<!-- should this be global? putting docstrings/comment is global -->

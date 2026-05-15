# pitfalls

no: assert dict == dict
yes: assert dict['field'] == dict['field'] unless we know better

more later

# Test suite

```bash
uv run /* --env-file .env */ pytest -q
(uv run / uvx) ruff check / format
uv run basedpyright --level error # error to cut spam
# maybe uvx ty
```

or so i think.

<!-- if this file comes with every request, tell me, and you have perms to cut the files down. goo goo ga ga. use caveman skill (only) for repeated artifacts. -->
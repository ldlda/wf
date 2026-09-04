# Documentation workflow

Keep live documentation authoritative and short. Use
[`README.md`](README.md) as the index for current documentation.

## Before editing documentation

- Read the nearby live document and [`current_roadmap.md`](current_roadmap.md).
- Search for the concept and any filenames you plan to change.
- Preserve unrelated user changes in the worktree.

## Separate live and historical documents

Use these locations consistently:

- `superpowers/plans/` contains active executable implementation plans.
- `superpowers/specs/` contains current design contracts.
- `historical/` contains completed plans, superseded designs, and narrative
  history. Preserve the original path below `historical/` when practical.

When work finishes, check every box in its implementation plan and move the
plan to `historical/`. Update live links after moving or retiring a document.
Search at least `README.md`, `current_roadmap.md`, `../skills/`, and nearby
architecture documents.

Update a specification in place while it remains the current contract. Move it
to `historical/` when it only explains how the code reached its current shape.
Keep one source of truth for current behavior.

## Keep the roadmap live

Limit `current_roadmap.md` to the current product shape, active work, next
priorities, durable constraints, and pointers to historical detail. Move
completed narratives out of the roadmap. If it exceeds 300 lines, trim it
before adding another section.

## Keep code and documentation consistent

Update user-facing documentation and repository skills when behavior changes.
If a live document describes a partial implementation, add a short comment or
docstring at the code seam. Future agents usually encounter code first.

## Verify Markdown edits

Run Markdown lint on the exact files you changed:

```powershell
$changedMarkdown = @(
    'docs/path/to/changed-file.md'
    'skills/path/to/another-changed-file.md'
)
pnpx markdownlint-cli2 $changedMarkdown
```

Replace the example paths with every Markdown file changed in the current
worktree. Use narrow lint or fix targets. Broad autofixes can rewrite
historical files or unrelated user changes.

Follow CommonMark list indentation. When a Markdown example contains fenced
code, wrap the outer example in a fence of four or more backticks.

Treat excerpt-only Python blocks as prose examples, not formatter input. For
example, Ruff can reinterpret a lone `arg3=None,` argument fragment as an
assignment because the surrounding call is absent.

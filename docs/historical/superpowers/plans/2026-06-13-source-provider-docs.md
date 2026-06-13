# Source Provider Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make source-provider setup understandable by moving provider/auth guidance into dedicated docs and linking the existing Python source runbook from the main docs.

**Architecture:** Keep `docs/wf_cli.md` as command reference, not a provider manual. Create one focused source-provider guide under `docs/`, keep `docs/runbooks/python-source.md` as the executable Python source walkthrough, and add a small documentation-link test so the main docs do not drift.

**Tech Stack:** Markdown docs, pytest doc-link smoke test, existing CLI/source terminology.

---

## File Structure

- Create `docs/source_provider_guide.md`: practical guide for MCP HTTP, MCP stdio, Python sources, auth refs, diagnostics, and Drive MCP caveat.
- Modify `docs/wf_cli.md`: replace the long Google Drive setup block with a short pointer to the provider guide; keep command references.
- Modify `docs/project_map.md`: add the provider guide to source architecture references.
- Modify `docs/current_roadmap.md`: mark provider docs completed.
- Create `tests/docs/test_docs_links.py`: lightweight test that important live docs link to provider/runbook docs.

---

### Task 1: Add Provider Guide

**Files:**
- Create: `docs/source_provider_guide.md`

- [ ] **Step 1: Create the guide**

Create `docs/source_provider_guide.md` with this content:

````markdown
# Source Provider Guide

Sources are the boundary where workflows call outside capability providers.
The current provider families are:

- `mcp`: MCP tools/resources/prompts exposed as workflow capabilities.
- `python`: trusted in-process Python `NodeSpec` registries.
- built-in sources such as `wf.std`.

Use `wf source diagnose <source_id>` before debugging capability calls. It
reports transport kind, auth reference, auth record presence, auth scheme
compatibility, catalog snapshot counts, and non-secret diagnostics.

## MCP HTTP Source

Use HTTP MCP for remote MCP servers:

```json
{
  "kind": "mcp",
  "id": "vendor.default",
  "provider": "vendor",
  "account": "default",
  "transport": {
    "kind": "http",
    "url": "https://example.test/mcp"
  },
  "auth_ref": "vendor.default"
}
```

Supported HTTP auth schemes:

- `bearer`
- `headers`
- `oauth_refresh_token`

Check it:

```bash
wf --config wf.config.json source diagnose vendor.default
```

## MCP Stdio Source

Use stdio MCP for local subprocess servers:

```json
{
  "kind": "mcp",
  "id": "everything.default",
  "provider": "everything",
  "account": "default",
  "transport": {
    "kind": "stdio",
    "command": "uvx",
    "args": ["mcp-server-everything"]
  }
}
```

For stdio auth, use `env` auth so secrets become subprocess environment
variables. HTTP bearer/OAuth auth is intentionally not applied to stdio
transports.

## Python Source

Python sources expose trusted in-process `NodeSpec` registries:

```json
{
  "kind": "python",
  "id": "local.ops",
  "path": ".",
  "module": "ops",
  "registry": "registry"
}
```

For the full runnable flow, see
[`Python Source Runbook`](runbooks/python-source.md).

## Auth Records And `auth_ref`

Source configs never store secret payloads directly. They point at an auth
record:

```json
{
  "auth_ref": "vendor.default"
}
```

Local/dev auth records are managed with:

```bash
wf admin auth save vendor.default --scheme bearer --payload-file auth.json
wf admin auth inspect vendor.default
wf admin auth delete vendor.default --confirm
```

Auth inspect/list responses show ids, schemes, metadata, and payload keys only.
Payload values are write-only.

## OAuth Refresh-Token Auth

Use `oauth_refresh_token` for HTTP providers where the platform can refresh an
access token and apply `Authorization: Bearer <access_token>` to MCP HTTP
requests.

Provider profiles live in config under `auth.providers`:

```json
{
  "auth": {
    "providers": {
      "google": {
        "kind": "oauth_authorization_code_pkce",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
        "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"]
      }
    }
  }
}
```

Login:

```bash
wf --config wf.config.json admin auth oauth-login google --id vendor.default
```

The stored refresh token is sensitive. The local file auth store is plaintext
and intended for local/dev use only.

## Google Drive MCP Caveat

Google Drive MCP is useful as a real remote MCP provider, but it is not a good
regression fixture. In local testing it showed provider-specific permission
friction and very low Drive MCP quota compared with the Drive REST API.

Use deterministic local fixtures for auth/runtime regression tests. Treat
Google Drive MCP as manual smoke coverage only.

## Diagnostic Loop

When a source call fails:

```bash
wf source diagnose <source_id>
wf source inspect <source_id>
wf cap list --source <source_id>
wf cap call <source_id>.<capability> --input '{}' --format compact
```

Use `wf --verbose ...` only when compact CLI errors are not enough.
````

- [ ] **Step 2: Commit the new guide**

Run:

```bash
git add docs/source_provider_guide.md
git commit -m "docs: add source provider guide"
```

---

### Task 2: Trim CLI Reference And Link Guide

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/project_map.md`

- [ ] **Step 1: Update `docs/wf_cli.md`**

In `docs/wf_cli.md`, keep the `### Diagnose A Source` section. Replace the long `### Google Drive MCP OAuth Setup` section with:

```markdown
### Source Provider Setup

For MCP HTTP, MCP stdio, Python source, `auth_ref`, and OAuth setup examples,
see the [`Source Provider Guide`](source_provider_guide.md).

Google Drive MCP is documented there as manual smoke coverage only; do not use
it as a regression fixture.
```

Do not remove the `Local/dev auth records` section. It is command reference and should stay in `wf_cli.md`.

- [ ] **Step 2: Update `docs/project_map.md`**

After the source architecture sentence near the top, add:

```markdown
For source provider setup examples, see
[`source_provider_guide.md`](source_provider_guide.md).
```

- [ ] **Step 3: Commit docs links**

Run:

```bash
git add docs/wf_cli.md docs/project_map.md
git commit -m "docs: link source provider guide"
```

---

### Task 3: Add Documentation Link Smoke Test

**Files:**
- Create: `tests/docs/test_docs_links.py`

- [ ] **Step 1: Create docs test**

Create `tests/docs/test_docs_links.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read_doc(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_cli_docs_link_source_provider_guide() -> None:
    text = _read_doc("docs/wf_cli.md")

    assert "source_provider_guide.md" in text
    assert "Source Provider Guide" in text


def test_project_map_links_source_provider_guide() -> None:
    text = _read_doc("docs/project_map.md")

    assert "source_provider_guide.md" in text


def test_source_provider_guide_links_python_runbook() -> None:
    text = _read_doc("docs/source_provider_guide.md")

    assert "runbooks/python-source.md" in text
    assert "wf source diagnose" in text
```

- [ ] **Step 2: Run docs test**

Run:

```bash
uv run pytest tests/docs/test_docs_links.py -q
```

Expected: 3 tests pass.

- [ ] **Step 3: Run docs-focused lint**

Run:

```bash
uv run ruff check tests/docs/test_docs_links.py
uv run basedpyright --level error tests/docs/test_docs_links.py
```

Expected: ruff passes and basedpyright reports 0 errors.

- [ ] **Step 4: Commit test**

```bash
git add tests/docs/test_docs_links.py
git commit -m "test: guard source provider doc links"
```

---

### Task 4: Roadmap And Final Verification

**Files:**
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, add a completed item near the source/auth diagnostics entry:

```markdown
- Completed source provider docs: `docs/source_provider_guide.md` now covers
  MCP HTTP, MCP stdio, Python sources, auth refs, OAuth refresh-token setup,
  diagnostics, and the Google Drive MCP caveat.
```

- [ ] **Step 2: Run final verification**

Run:

```bash
uv run pytest tests/docs/test_docs_links.py -q
uv run ruff check tests/docs/test_docs_links.py
uv run basedpyright --level error tests/docs/test_docs_links.py
git diff --check
```

Expected:

- `3 passed`
- `ruff`: all checks passed
- `basedpyright`: 0 errors
- `git diff --check`: no whitespace errors; CRLF warnings are acceptable on Windows

- [ ] **Step 3: Commit roadmap**

```bash
git add docs/current_roadmap.md
git commit -m "docs: record source provider docs"
```

---

## Self-Review

- Spec coverage: plan adds a source provider guide, links it from CLI docs/project map, preserves Python runbook, documents Drive MCP as manual-only, and adds doc-link tests.
- Placeholder scan: no TBD/TODO/fill-in placeholders remain.
- Type consistency: test paths and doc filenames match the plan: `docs/source_provider_guide.md`, `docs/runbooks/python-source.md`, and `tests/docs/test_docs_links.py`.


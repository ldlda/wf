# OAuth Login Auth Records Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local/dev OAuth login command that uses provider profiles to create typed `oauth_refresh_token` auth records for sources such as Google Drive MCP.

**Architecture:** OAuth login is admin/CLI setup, not runtime execution. Provider profiles describe how to start authorization-code + PKCE login. The resulting refresh token is saved as a typed auth record. Runtime source calls continue to consume auth records through source-owned binders from the previous slice.

**Tech Stack:** Python 3.14, Typer, Authlib (new dependency if accepted), pytest, basedpyright, ruff, local callback or pasted redirect URL flow.

---

## Dependency On Previous Slice

This plan assumes `docs/superpowers/plans/2026-06-13-typed-auth-records-and-mcp-binder.md` is complete:

- `wf_api.auth.StoredAuthRecord`
- `wf_api.auth.OAuthRefreshTokenAuth`
- auth store can save typed records
- MCP runtime can use typed records through `McpAuthBinder`

Do not implement this plan first.

## File Structure

- Modify `src/wf_config/models.py`: add OAuth provider profile config models under a top-level auth config section.
- Modify `src/wf_config/loader.py` only if config-relative loading needs provider profile defaults.
- Create `src/wf_cli/oauth.py`: OAuth login flow helpers and provider profile DTOs for CLI use.
- Modify `src/wf_cli/commands/auth_admin.py`: add `oauth-login` command.
- Modify `src/wf_cli/context.py` only if CLI context must expose loaded workflow config auth providers.
- Add tests:
  - `tests/wf_config/test_config_models.py`
  - `tests/wf_cli/test_auth_oauth_login.py`
- Docs:
  - `docs/wf_cli.md`
  - `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`
  - `docs/current_roadmap.md`

## Task 1: OAuth Provider Profile Config

**Files:**
- Modify: `src/wf_config/models.py`
- Modify: `src/wf_config/__init__.py`
- Test: `tests/wf_config/test_config_models.py`

- [ ] **Step 1: Add failing config model test**

Append:

```python
from wf_config import WorkflowConfigFile


def test_workflow_config_parses_oauth_provider_profile() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "auth": {
                "providers": {
                    "google": {
                        "kind": "oauth_authorization_code_pkce",
                        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
                        "token_url": "https://oauth2.googleapis.com/token",
                        "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
                        "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
                        "scopes": [
                            "https://www.googleapis.com/auth/drive.readonly",
                        ],
                    }
                }
            }
        }
    )

    provider = config.auth.providers["google"]
    assert provider.kind == "oauth_authorization_code_pkce"
    assert provider.client_id_env == "GOOGLE_OAUTH_CLIENT_ID"
    assert provider.scopes == ("https://www.googleapis.com/auth/drive.readonly",)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py::test_workflow_config_parses_oauth_provider_profile -q
```

Expected: fails because `auth` config does not exist.

- [ ] **Step 3: Implement config models**

In `src/wf_config/models.py`, add:

```python
class OAuthProviderConfig(BaseModel):
    kind: Literal["oauth_authorization_code_pkce"]
    auth_url: AnyUrl
    token_url: AnyUrl
    client_id_env: str
    client_secret_env: str | None = None
    scopes: tuple[str, ...] = ()
    redirect_uri: str = "http://127.0.0.1:0/oauth/callback"


class AuthConfig(BaseModel):
    providers: dict[str, OAuthProviderConfig] = Field(default_factory=dict)
```

Add `auth: AuthConfig = Field(default_factory=AuthConfig)` to `WorkflowConfigFile`.

Export `AuthConfig` and `OAuthProviderConfig` in `src/wf_config/__init__.py`.

- [ ] **Step 4: Run config tests**

Run:

```bash
uv run pytest tests/wf_config/test_config_models.py -q
uv run basedpyright --level error src/wf_config tests/wf_config/test_config_models.py
uv run ruff check src/wf_config tests/wf_config/test_config_models.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_config/models.py src/wf_config/__init__.py tests/wf_config/test_config_models.py
git commit -m "feat: add oauth provider config"
```

## Task 2: OAuth Login Flow Helper

**Files:**
- Create: `src/wf_cli/oauth.py`
- Test: `tests/wf_cli/test_auth_oauth_login.py`

- [ ] **Step 1: Add failing helper tests**

Create `tests/wf_cli/test_auth_oauth_login.py`:

```python
from __future__ import annotations

import pytest

from wf_cli.oauth import OAuthLoginResult, build_oauth_record
from wf_config import OAuthProviderConfig
from wf_api.auth import OAuthRefreshTokenAuth


def test_build_oauth_record_creates_refresh_token_auth() -> None:
    provider = OAuthProviderConfig(
        kind="oauth_authorization_code_pkce",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id_env="GOOGLE_OAUTH_CLIENT_ID",
        client_secret_env="GOOGLE_OAUTH_CLIENT_SECRET",
        scopes=("https://www.googleapis.com/auth/drive.readonly",),
    )
    result = OAuthLoginResult(
        refresh_token="refresh",
        subject="user@example.com",
        scopes=("https://www.googleapis.com/auth/drive.readonly",),
    )

    record = build_oauth_record(
        auth_ref="google.drive.personal",
        provider_name="google",
        provider=provider,
        client_id="client",
        client_secret="secret",
        result=result,
    )

    assert record.id == "google.drive.personal"
    assert isinstance(record.auth, OAuthRefreshTokenAuth)
    assert record.auth.client_id == "client"
    assert record.auth.client_secret == "secret"
    assert record.auth.refresh_token == "refresh"
    assert record.metadata["provider"] == "google"
    assert record.metadata["subject"] == "user@example.com"


def test_build_oauth_record_rejects_missing_refresh_token() -> None:
    provider = OAuthProviderConfig(
        kind="oauth_authorization_code_pkce",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id_env="GOOGLE_OAUTH_CLIENT_ID",
    )

    with pytest.raises(ValueError, match="refresh token"):
        build_oauth_record(
            auth_ref="google.drive.personal",
            provider_name="google",
            provider=provider,
            client_id="client",
            client_secret=None,
            result=OAuthLoginResult(refresh_token=None),
        )
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_auth_oauth_login.py -q
```

Expected: fails because `wf_cli.oauth` does not exist.

- [ ] **Step 3: Implement minimal helper**

Create `src/wf_cli/oauth.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from wf_api.auth import OAuthRefreshTokenAuth, StoredAuthRecord
from wf_config import OAuthProviderConfig


@dataclass(frozen=True, slots=True)
class OAuthLoginResult:
    refresh_token: str | None
    subject: str | None = None
    scopes: tuple[str, ...] = ()


def build_oauth_record(
    *,
    auth_ref: str,
    provider_name: str,
    provider: OAuthProviderConfig,
    client_id: str,
    client_secret: str | None,
    result: OAuthLoginResult,
) -> StoredAuthRecord:
    if not result.refresh_token:
        raise ValueError("OAuth login did not return a refresh token")
    metadata: dict[str, object] = {"provider": provider_name}
    if result.subject:
        metadata["subject"] = result.subject
    if result.scopes:
        metadata["scopes"] = list(result.scopes)
    return StoredAuthRecord(
        id=auth_ref,
        auth=OAuthRefreshTokenAuth(
            client_id=client_id,
            client_secret=client_secret or "",
            refresh_token=result.refresh_token,
            token_url=provider.token_url,
            scopes=tuple(result.scopes or provider.scopes),
        ),
        metadata=metadata,
    )
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
uv run pytest tests/wf_cli/test_auth_oauth_login.py -q
uv run basedpyright --level error src/wf_cli/oauth.py tests/wf_cli/test_auth_oauth_login.py
uv run ruff check src/wf_cli/oauth.py tests/wf_cli/test_auth_oauth_login.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_cli/oauth.py tests/wf_cli/test_auth_oauth_login.py
git commit -m "feat: build oauth auth records"
```

## Task 3: Interactive OAuth Exchange Abstraction

**Files:**
- Modify: `src/wf_cli/oauth.py`
- Test: `tests/wf_cli/test_auth_oauth_login.py`

- [ ] **Step 1: Add failing test with fake OAuth client**

Append:

```python
from wf_cli.oauth import OAuthCodeLoginFlow


class _FakeOAuthClient:
    def __init__(self) -> None:
        self.authorization_url = "https://auth.example/authorize?state=abc"
        self.fetch_calls: list[str] = []

    def create_authorization_url(self, auth_url: str, **kwargs: object) -> tuple[str, str]:
        assert auth_url == "https://accounts.google.com/o/oauth2/v2/auth"
        return self.authorization_url, "state-123"

    async def fetch_token(self, token_url: str, authorization_response: str) -> dict[str, object]:
        self.fetch_calls.append(authorization_response)
        return {
            "refresh_token": "refresh",
            "scope": "https://www.googleapis.com/auth/drive.readonly",
        }


async def test_oauth_code_login_flow_uses_injected_client() -> None:
    provider = OAuthProviderConfig(
        kind="oauth_authorization_code_pkce",
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id_env="GOOGLE_OAUTH_CLIENT_ID",
        scopes=("https://www.googleapis.com/auth/drive.readonly",),
    )
    client = _FakeOAuthClient()
    flow = OAuthCodeLoginFlow(client_factory=lambda **kwargs: client)

    result = await flow.login_with_authorization_response(
        provider=provider,
        client_id="client",
        client_secret=None,
        authorization_response="http://127.0.0.1/callback?code=abc&state=state-123",
    )

    assert result.refresh_token == "refresh"
    assert result.scopes == ("https://www.googleapis.com/auth/drive.readonly",)
    assert client.fetch_calls == ["http://127.0.0.1/callback?code=abc&state=state-123"]
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_auth_oauth_login.py::test_oauth_code_login_flow_uses_injected_client -q
```

Expected: fails because `OAuthCodeLoginFlow` does not exist.

- [ ] **Step 3: Implement injectable OAuth flow**

In `src/wf_cli/oauth.py`, add:

```python
from collections.abc import Callable
from typing import Any, Protocol


class OAuthClientLike(Protocol):
    def create_authorization_url(self, auth_url: str, **kwargs: object) -> tuple[str, str]: ...
    async def fetch_token(self, token_url: str, authorization_response: str) -> dict[str, object]: ...


OAuthClientFactory = Callable[..., OAuthClientLike]


class OAuthCodeLoginFlow:
    def __init__(self, client_factory: OAuthClientFactory) -> None:
        self._client_factory = client_factory

    async def login_with_authorization_response(
        self,
        *,
        provider: OAuthProviderConfig,
        client_id: str,
        client_secret: str | None,
        authorization_response: str,
    ) -> OAuthLoginResult:
        client = self._client_factory(
            client_id=client_id,
            client_secret=client_secret,
            scope=" ".join(provider.scopes),
            code_challenge_method="S256",
        )
        client.create_authorization_url(str(provider.auth_url))
        token = await client.fetch_token(
            str(provider.token_url),
            authorization_response=authorization_response,
        )
        refresh_token = token.get("refresh_token")
        if refresh_token is not None and not isinstance(refresh_token, str):
            raise ValueError("OAuth refresh_token must be a string")
        raw_scope = token.get("scope")
        scopes = tuple(str(raw_scope).split()) if raw_scope else provider.scopes
        return OAuthLoginResult(refresh_token=refresh_token, scopes=scopes)
```

This helper supports pasted authorization response first. Browser callback can be a later refinement.

- [ ] **Step 4: Run helper tests**

Run:

```bash
uv run pytest tests/wf_cli/test_auth_oauth_login.py -q
uv run basedpyright --level error src/wf_cli/oauth.py tests/wf_cli/test_auth_oauth_login.py
uv run ruff check src/wf_cli/oauth.py tests/wf_cli/test_auth_oauth_login.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_cli/oauth.py tests/wf_cli/test_auth_oauth_login.py
git commit -m "feat: add oauth code login helper"
```

## Task 4: CLI Command `wf admin auth oauth-login`

**Files:**
- Modify: `src/wf_cli/commands/auth_admin.py`
- Test: `tests/wf_cli/test_auth_oauth_login.py`

- [ ] **Step 1: Add failing CLI test with fake flow**

Append:

```python
from typer.testing import CliRunner

from wf_cli.app import app


def test_auth_oauth_login_saves_record_from_provider_profile(monkeypatch, tmp_path) -> None:
    saved: list[object] = []

    class _FakeAdmin:
        async def save_auth_record(self, **kwargs: object) -> dict[str, object]:
            saved.append(kwargs)
            return {"id": kwargs["auth_ref"], "scheme": "oauth_refresh_token"}

    class _FakeContext:
        admin = _FakeAdmin()

    async def _fake_login(*args: object, **kwargs: object) -> OAuthLoginResult:
        return OAuthLoginResult(refresh_token="refresh")

    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda ctx: _FakeContext(),
    )
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin._login_with_pasted_response",
        _fake_login,
    )

    config_path = tmp_path / "wf.config.json"
    config_path.write_text(
        json.dumps(
            {
                "auth": {
                    "providers": {
                        "google": {
                            "kind": "oauth_authorization_code_pkce",
                            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
                            "token_url": "https://oauth2.googleapis.com/token",
                            "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
                            "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client")

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config_path),
            "admin",
            "auth",
            "oauth-login",
            "google",
            "--id",
            "google.drive.personal",
            "--authorization-response",
            "http://127.0.0.1/callback?code=abc&state=state",
        ],
    )

    assert result.exit_code == 0, result.output
    assert saved
    assert saved[0]["auth_ref"] == "google.drive.personal"
    assert saved[0]["scheme"] == "oauth_refresh_token"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_auth_oauth_login.py::test_auth_oauth_login_saves_record_from_provider_profile -q
```

Expected: fails because command does not exist.

- [ ] **Step 3: Implement CLI command**

In `src/wf_cli/commands/auth_admin.py`, add command `oauth-login`.

Implementation outline:

```python
@app.command("oauth-login")
def oauth_login(
    ctx: typer.Context,
    provider_name: Annotated[str, typer.Argument(help="Auth provider profile name.")],
    auth_ref: Annotated[str, typer.Option("--id", help="Auth record id/ref to save.")],
    authorization_response: Annotated[
        str,
        typer.Option("--authorization-response", help="Full redirected callback URL after login."),
    ],
) -> None:
    workflow_config = load_workflow_config_from_typer(ctx)
    provider = workflow_config.auth.providers.get(provider_name)
    if provider is None:
        raise typer.BadParameter(f"unknown auth provider {provider_name!r}")
    client_id = os.environ.get(provider.client_id_env)
    if not client_id:
        raise typer.BadParameter(f"missing env var {provider.client_id_env}")
    client_secret = (
        os.environ.get(provider.client_secret_env)
        if provider.client_secret_env is not None
        else None
    )
    result = run_cli_operation(
        load_cli_context_from_typer(ctx),
        _login_with_pasted_response(
            provider=provider,
            client_id=client_id,
            client_secret=client_secret,
            authorization_response=authorization_response,
        ),
    )
    record = build_oauth_record(...)
    context = load_cli_context_from_typer(ctx)
    saved = run_cli_operation(
        context,
        context.admin.save_auth_record(
            auth_ref=record.id,
            scheme="oauth_refresh_token",
            payload=record.auth.model_dump(mode="json", exclude={"kind"}),
            metadata=record.metadata,
        ),
    )
    emit_json(saved)
```

Use existing config loading helpers from `wf_cli.context` if available. If not available, add a small helper in this command module that reads `ctx.params["config"]` or the existing config option path used by `load_cli_context_from_typer`.

Add `_login_with_pasted_response()` wrapper so tests can monkeypatch it:

```python
async def _login_with_pasted_response(...) -> OAuthLoginResult:
    from authlib.integrations.httpx_client import AsyncOAuth2Client

    flow = OAuthCodeLoginFlow(client_factory=AsyncOAuth2Client)
    return await flow.login_with_authorization_response(...)
```

If `authlib` is not yet a dependency, add it with `uv add authlib` in a separate commit or update `pyproject.toml` manually according to project style.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_auth_oauth_login.py tests/wf_cli/test_auth_admin.py -q
uv run basedpyright --level error src/wf_cli/commands/auth_admin.py src/wf_cli/oauth.py tests/wf_cli/test_auth_oauth_login.py
uv run ruff check src/wf_cli/commands/auth_admin.py src/wf_cli/oauth.py tests/wf_cli/test_auth_oauth_login.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_cli/commands/auth_admin.py src/wf_cli/oauth.py tests/wf_cli/test_auth_oauth_login.py pyproject.toml uv.lock
git commit -m "feat: add oauth login auth command"
```

## Task 5: Google Drive MCP Docs And Smoke Instructions

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Document config**

Add a section to `docs/wf_cli.md`:

```md
### Google Drive MCP OAuth Setup

Google Drive MCP is a remote HTTP MCP source:

```json
{
  "sources": [
    {
      "id": "google.drive",
      "kind": "mcp",
      "transport": {
        "kind": "http",
        "url": "https://drivemcp.googleapis.com/mcp/v1"
      },
      "auth_ref": "google.drive.personal"
    }
  ],
  "auth": {
    "providers": {
      "google": {
        "kind": "oauth_authorization_code_pkce",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id_env": "GOOGLE_OAUTH_CLIENT_ID",
        "client_secret_env": "GOOGLE_OAUTH_CLIENT_SECRET",
        "scopes": [
          "https://www.googleapis.com/auth/drive.readonly"
        ]
      }
    }
  }
}
```

Run OAuth login:

```bash
wf --config wf.config.json admin auth oauth-login google --id google.drive.personal --authorization-response "<redirected URL>"
```
```

Mention that refresh tokens are sensitive and file store is plaintext local/dev only.

- [ ] **Step 2: Update spec/roadmap status**

In the auth spec, mark OAuth login as implemented if this slice is done. In roadmap, update auth line so Google Drive smoke remains optional/manual if credentials are local-only.

- [ ] **Step 3: Run docs-adjacent verification**

Run:

```bash
uv run pytest tests/wf_cli/test_auth_oauth_login.py tests/wf_config/test_config_models.py -q
uv run ruff check src/wf_cli src/wf_config tests/wf_cli/test_auth_oauth_login.py
uv run basedpyright --level error src/wf_cli/oauth.py src/wf_cli/commands/auth_admin.py src/wf_config
git diff --check
```

Expected: tests pass, lint/typecheck clean, no whitespace errors except acceptable CRLF warnings on Windows.

- [ ] **Step 4: Commit**

```bash
git add docs/wf_cli.md docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md docs/current_roadmap.md
git commit -m "docs: document oauth auth login"
```

## Self-Review Checklist

- Spec coverage: provider profiles, typed refresh-token records, CLI login, and Drive MCP setup are covered.
- Placeholder scan: no TODO/TBD placeholders.
- Type consistency: plan consistently uses `OAuthProviderConfig`, `OAuthCodeLoginFlow`, `OAuthLoginResult`, and `StoredAuthRecord`.
- Scope check: browser-opening/local callback UX is intentionally not required in this slice; pasted authorization response is enough for a verifiable first pass.

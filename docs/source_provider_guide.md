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
  "module": "my_source.ops",
  "registry": "registry"
}
```

Package-style modules are preferred. Relative imports inside the configured
package are source-local; bare local imports use Python's normal global import
cache and can collide if multiple sources reuse names like `ops` or `helpers`.

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
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"],
        "extra_authorize_params": {
          "access_type": "offline",
          "prompt": "consent"
        }
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

## Source Resource Refs

Resource refs are inert workflow data:

```json
{
  "kind": "source_resource_ref",
  "logical_source": "drive",
  "uri": "demo://docs/welcome"
}
```

Input/output/state bindings treat this object as ordinary JSON. Only explicit
platform helper nodes such as `wf.source.read_resource` dereference it. This
keeps large MCP resource payloads out of workflow state unless the workflow asks
for them.

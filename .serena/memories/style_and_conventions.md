# Style And Conventions

General:
- Python 3.14, `src/` layout, Pydantic v2 where external/boundary validation is useful.
- Prefer explicit dataclasses for runtime/internal models and Pydantic for config/wire-ish boundary validation.
- Async-first for MCP calls and workflow runtime interactions.
- Keep MCP proxy concepts separate from workflow-specific concepts like `outcome`.
- Do not leak workflow-only fields into MCP `tools/list`.

MCP/proxy conventions:
- Transparent proxy mode is the product path; old broker mode is secondary/debug/admin-oriented.
- Admin tools live under the reserved namespace `wf.mcp_*`.
- Upstream FastMCP names use Namespace behavior: `<connection_id>_<local_tool_name>`, e.g. `everything.default_echo`.
- Keep name parsing and unmangling in `names.py`; do not scatter string slicing across modules.
- Keep cursor mechanics in `pagination.py`; use opaque cursors and `nextCursor` to mirror MCP pagination style.
- Keep config disk writes in `config_manager.py`; transparent proxy code should expose/administer behavior, not own JSON mutation details.
- `wf_mcp.config.json` is user-owned live config. Do not edit/revert it unless explicitly asked.

Code style:
- Use precise type hints and modern Python collection syntax (`list[str]`, `dict[str, Any]`).
- Keep modules layered by responsibility; avoid stuffing everything into service/runtime files.
- Prefer small helper modules when behavior becomes a boundary (`config_models.py`, `config_manager.py`, `proxy_validation.py`, `names.py`, `pagination.py`).
- Validation should fail early with clear errors.
- Tests should exercise behavior through public APIs/MCP calls where practical.
- For MCP client `CallToolResult.structured_content`, guard for `None` in tests before subscripting; use helper assertions where useful.

Editing rules from repo collaboration:
- Use `apply_patch` for manual code edits.
- Do not revert user-owned changes.
- Direct Serena MCP is available and can be used for semantic navigation/editing; onboarding is already complete.
# Style And Conventions

General:
- Python 3.14, `src/` layout, Pydantic v2 where external/boundary validation is useful.
- Prefer explicit dataclasses for runtime/internal models and Pydantic for config/wire-ish boundary validation.
- Async-first for MCP calls and workflow runtime interactions.
- Keep MCP proxy concepts separate from workflow-specific concepts like `outcome`.
- Do not leak workflow-only fields into MCP `tools/list`.

Code style:
- Use precise type hints and modern Python collection syntax (`list[str]`, `dict[str, Any]`).
- Keep modules layered by responsibility; avoid stuffing everything into service/runtime files.
- Prefer small helper modules when behavior becomes a boundary (`config_models.py`, `config_manager.py`, `proxy_validation.py`).
- Validation should fail early with clear errors.
- Tests should exercise behavior through public APIs/MCP calls where practical.

Editing rules from repo collaboration:
- Use `apply_patch` for manual code edits.
- Do not revert user-owned changes.
- Treat `wf_mcp.config.json` as user-owned live config unless explicitly asked.
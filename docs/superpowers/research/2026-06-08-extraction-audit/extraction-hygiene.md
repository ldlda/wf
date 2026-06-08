# Extraction Hygiene Audit

Date: 2026-06-08

Auditor: opencode (mimo-v2.5-free)

Scope: `src/wf_sources_mcp/**`, `src/wf_mcp/**` compatibility shims,
`docs/current_roadmap.md`, `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`,
`docs/superpowers/research/2026-06-07-wf-mcp-runtime-source-provider-map.md`

---

## Summary

The `wf_sources_mcp` extraction is in good shape. The package is now **fully
self-contained** -- it imports nothing from `wf_mcp` at runtime or
`TYPE_CHECKING`. The dependency direction is exclusively `wf_mcp` -> `wf_sources_mcp`.

Key achievements since the 2026-06-07 research map:
- `parse_connection_id` and `RESERVED_CONNECTION_IDS` are canonical in
  `wf_sources_mcp.ids` (no more `wf_mcp.connections` or `wf_mcp.shared.names`
  dependency).
- `McpSourceConnection` replaces `ConnectionConfig` in all `wf_sources_mcp`
  runtime code.
- `open_mcp_session` is canonical in `wf_sources_mcp.client.transport`.
- Runtime, SDK adapter, catalog, discovery, schema models, tool events, tool
  wrappers, and adapters are all canonical in `wf_sources_mcp`.

The remaining items are stale docs/comments, minor shim hygiene, and
future-work boundary decisions. Nothing is a correctness issue today.

---

## Findings

### F1: `wf_mcp.sdk.base.py` docstring is stale

**File:** `src/wf_mcp/sdk/base.py:1-4`
**Content:** `"""Compatibility shim for MCP upstream SDK protocol/result types.\nCanonical implementation lives in \`wf_sources_mcp.sdk\`."""`
**Status:** Stale. The docstring says canonical lives in `wf_sources_mcp.sdk`, which is
correct, but `wf_mcp.sdk.base` is not referenced by any other code. It is a
dead re-export module.

**Category:** hygiene
**Fix:** Safe to delete now. No code imports from `wf_mcp.sdk.base`.

---

### F2: `wf_mcp.storage` shim has stale docstring

**File:** `src/wf_mcp/storage/__init__.py` (re-exports from `wf_sources_mcp.storage`)
**Content:** No docstring present. The `__init__.py` just re-exports.

**Category:** docs-only
**Fix:** Defer. No functional issue. The shim is correct.

---

### F3: `wf_mcp.workflow_surface/constants.py` docstring says "during extraction"

**File:** `src/wf_mcp/workflow_surface/constants.py:1-7`
**Content:** `"""Compatibility shim for workflow API constants.\nNew code should import these literals from \`wf_api.constants\`. This module stays\nso older MCP workflow-surface imports keep working during extraction."""`
**Status:** Stale. The extraction of `wf_api.constants` is complete. The phrase
"during extraction" implies the shim is temporary. In fact, the shim is
intentional long-lived compatibility infrastructure until MCP callers migrate.

**Category:** docs-only
**Fix:** Safe to fix now. Replace "during extraction" with "until callers migrate".

---

### F4: `wf_mcp.workflow_surface/refs.py` docstring says "during extraction"

**File:** `src/wf_mcp/workflow_surface/refs.py:1-6`
**Content:** Same pattern as F3.

**Category:** docs-only
**Fix:** Safe to fix now.

---

### F5: `wf_mcp.workflow_surface/next_actions.py` docstring says "during extraction"

**File:** `src/wf_mcp/workflow_surface/next_actions.py:1-6`
**Content:** Same pattern as F3.

**Category:** docs-only
**Fix:** Safe to fix now.

---

### F6: `wf_mcp.workflow_surface/wrapper_hints.py` docstring says "during extraction"

**File:** `src/wf_mcp/workflow_surface/wrapper_hints.py:1-6`
**Content:** Same pattern as F3.

**Category:** docs-only
**Fix:** Safe to fix now.

---

### F7: `wf_mcp.workflow_surface/runtime_dependencies.py` docstring says "during extraction"

**File:** `src/wf_mcp/workflow_surface/runtime_dependencies.py:1-6`
**Content:** Same pattern as F3.

**Category:** docs-only
**Fix:** Safe to fix now.

---

### F8: `wf_mcp.workflow_surface/saved_subgraphs.py` docstring says "during extraction"

**File:** `src/wf_mcp/workflow_surface/saved_subgraphs.py:1-6`
**Content:** `"""Compatibility shim -- canonical implementation moved to wf_api.saved_subgraphs.\nThis module re-exports every public symbol so that existing\n\`\`from wf_mcp.workflow_surface.saved_subgraphs import ...\`\` continues to work\nwithout changes.  New code should import from \`\`wf_api.saved_subgraphs\`\`\ndirectly."""`
**Status:** This one is actually correct and well-worded. No action needed.

**Category:** docs-only
**Fix:** None needed.

---

### F9: `wf_mcp.workflow_surface/run_lifecycle.py` docstring is correct

**File:** `src/wf_mcp/workflow_surface/run_lifecycle.py:1-6`
**Content:** Same correct pattern as F8.

**Category:** docs-only
**Fix:** None needed.

---

### F10: `docs/superpowers/research/2026-06-07-wf-mcp-runtime-source-provider-map.md` has stale blocker claims

**File:** `docs/superpowers/research/2026-06-07-wf-mcp-runtime-source-provider-map.md`
**Line 115-118:** Claims `wf_mcp.runtime.factory`, `wf_mcp.runtime.pool`,
`wf_mcp.runtime.session` import `wf_mcp.models.ConnectionConfig` at runtime.
**Status:** These are now compatibility shims re-exporting from `wf_sources_mcp.runtime`.
The runtime modules in `wf_mcp.runtime.*` no longer contain original code -- they
are pure re-exports. The runtime code is now canonical in `wf_sources_mcp.runtime`.

**Line 116:** Claims `wf_mcp.sdk.adapter` imports `wf_mcp.models.ConnectionConfig` at
runtime. **Status:** Now a pure re-export shim from `wf_sources_mcp.sdk.adapter`.

**Category:** docs-only (historical research doc)
**Fix:** Defer. This is a historical snapshot. Add a note at the top saying the
analysis is from 2026-06-07 and some blockers have since been resolved.

---

### F11: `docs/superpowers/research/2026-06-07-wf-mcp-runtime-source-provider-map.md` claims `parse_connection_id` still lives in `wf_mcp.connections`

**File:** `docs/superpowers/research/2026-06-07-wf-mcp-runtime-source-provider-map.md`
**Lines 290-310 (Blocker 2):** States `parse_connection_id` lives in
`wf_mcp.connections` and `RESERVED_CONNECTION_IDS` in `wf_mcp.shared.names`.
**Status:** Both are now canonical in `wf_sources_mcp.ids`. The `wf_mcp.connections`
module imports from `wf_sources_mcp.ids` and is itself a compatibility shim.

**Category:** docs-only (stale claim)
**Fix:** Defer. Historical doc.

---

### F12: `wf_mcp.workflow/wrappers.py` has stale `_model_from_schema` alias

**File:** `src/wf_mcp/workflow/wrappers.py:10`
**Content:** `_model_from_schema = model_from_schema  # TODO: remove when callers migrate`
**Status:** This is a compatibility alias for callers that still import
`wf_mcp.workflow.wrappers._model_from_schema`. The TODO is stale if all callers
have migrated. No grep matches for `_model_from_schema` outside this file, so
the alias may be dead.

**Category:** hygiene
**Fix:** Safe to check and potentially remove. Needs caller search confirmation.

---

### F13: `wf_mcp.models` re-exports `CatalogSnapshot` and `dump_catalog_snapshot`

**File:** `src/wf_mcp/models.py:11`
**Content:** `from wf_sources_mcp.catalog.models import CatalogSnapshot, dump_catalog_snapshot`
**Status:** This re-export means `wf_mcp.models.CatalogSnapshot` still works.
However, `wf_sources_mcp.catalog.models` is the canonical location and
`wf_mcp.catalog.models` is the primary shim. Having both `wf_mcp.models` and
`wf_mcp.catalog.models` re-export the same types is redundant but not harmful.

**Category:** hygiene
**Fix:** Defer. Remove from `wf_mcp.models` when no callers remain.

---

### F14: `current_roadmap.md` says "specs_from_discovered_tools remains in wf_mcp"

**File:** `docs/current_roadmap.md`
**Lines ~339-346:** Multiple roadmap entries state `specs_from_discovered_tools`
remains in `wf_mcp`. This is accurate -- `wf_mcp.broker.discovery` still contains
the broker compatibility adapter that wraps the canonical
`wf_sources_mcp.discovery.specs_from_discovered_tools`. The `wf_mcp` version
converts `ConnectionConfig` to `McpSourceConnection` and projects events.

**Category:** docs-only (accurate but could be clearer)
**Fix:** Defer. The wording is technically correct; the canonical version is in
`wf_sources_mcp.discovery` and `wf_mcp.broker.discovery` is the broker adapter.

---

### F15: `current_roadmap.md` says "wf_mcp.broker.catalog retained as a compatibility shim"

**File:** `docs/current_roadmap.md`
**Lines ~333-334:** States `wf_mcp.broker.catalog` is retained as a shim.
**Status:** Correct. `src/wf_mcp/broker/catalog.py` re-exports
`CombinedCatalog` and `snapshot_from_specs` from `wf_sources_mcp.catalog`.

**Category:** docs-only (accurate)
**Fix:** None needed.

---

### F16: Historical plan `2026-06-07-mcp-client-session-opener.md` references old paths

**File:** `docs/historical/superpowers/plans/2026-06-07-mcp-client-session-opener.md:7`
**Content:** References `wf_mcp.sdk.adapter.McpSdkAdapter` and
`wf_mcp.runtime.factory.PersistentSessionFactory` as needing the shared opener.
**Status:** Now completed. Both `wf_mcp.sdk.adapter` and `wf_mcp.runtime.factory`
are pure re-export shims; the canonical code uses `open_mcp_session` from
`wf_sources_mcp.client.transport`.

**Category:** docs-only (historical plan, completed)
**Fix:** Defer. Historical plans are snapshots of the state at planning time.

---

### F17: Historical plan `2026-06-05-legacy-mcp-config-migration.md` references old paths

**File:** `docs/historical/superpowers/plans/2026-06-05-legacy-mcp-config-migration.md:7`
**Content:** References `wf_mcp.sdk.adapter` and `wf_mcp.runtime.factory` as
needing the flat connection metadata shape.
**Status:** Completed. The migration path works through `wf_config` ->
`workflow_mcp_source_to_connection_config` in `wf_mcp.source_registry`.

**Category:** docs-only (historical plan, completed)
**Fix:** Defer.

---

### F18: `wf_mcp.broker.discovery` imports `specs_from_discovered_tools` from `wf_sources_mcp`

**File:** `src/wf_mcp/broker/discovery.py:13-14`
**Content:** `from wf_sources_mcp.discovery import (\n    specs_from_discovered_tools as source_specs_from_discovered_tools,\n)`
**Status:** This is the correct broker adapter pattern. The broker version wraps
the canonical version with `ConnectionConfig` -> `McpSourceConnection` conversion
and event projection. No issue.

**Category:** docs-only (no issue)
**Fix:** None needed.

---

### F19: `wf_mcp.workflow_surface.handlers.py` docstring says "while the MCP surface is migrated"

**File:** `src/wf_mcp/workflow_surface/handlers.py:13-17`
**Content:** `"""Compatibility wrapper for old wf_mcp.workflow_surface imports.\n\nNew code should construct \`WorkflowApi(context_from_service(service))\`\ndirectly. This shim keeps tests and legacy broker artifact tools working\nwhile the MCP surface is migrated."""`
**Status:** Slightly stale. The `WorkflowSurfaceHandlers` shim is now the
documented compatibility path. The phrase "while the MCP surface is migrated"
implies the migration is in progress. It may be more accurate to say "for
legacy callers" instead.

**Category:** docs-only
**Fix:** Safe to fix now.

---

### F20: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md` references historical blocker state

**File:** `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
**Lines 134-146:** States `specs_from_discovered_tools` remains in `wf_mcp`
"until the event/wrapper seam is neutralized." The seam has since been neutralized
(slices 18-20 in the spec). The spec lists these as completed, but the phrasing
in earlier slices ("remains in wf_mcp until...") could mislead readers who only
scan the early items.

**Category:** docs-only (spec is internally consistent when read fully)
**Fix:** Defer. The spec is internally consistent; each slice says "Complete."

---

### F21: `docs/superpowers/research/2026-06-07-wf-mcp-runtime-source-provider-map.md` has stale "Next Slices" section

**File:** `docs/superpowers/research/2026-06-07-wf-mcp-runtime-source-provider-map.md`
**Lines 549-650 (Slice 0-6):** The recommended next slices are now mostly completed:
- Slice 0 (SourceConnection protocol): Completed via `McpSourceConnection`
- Slice 1 (parse_connection_id move): Completed to `wf_sources_mcp.ids`
- Slice 2 (open_mcp_session): Completed in `wf_sources_mcp.client.transport`
- Slice 3 (runtime move): Completed to `wf_sources_mcp.runtime`
- Slice 4 (adapter move): Completed to `wf_sources_mcp.sdk.adapter`

The research doc does not have completion markers, unlike the spec which does.

**Category:** docs-only (stale research artifact)
**Fix:** Defer. Historical research. Could add a note at the top.

---

### F22: `wf_mcp.broker.service.core.py` imports `SourceRegistryStore` from `wf_sources_mcp`

**File:** `src/wf_mcp/broker/service/core.py:26`
**Content:** `from wf_sources_mcp.source_registry import SourceRegistryStore`
**Status:** This is correct broker-consumes-source-provider direction. The broker
service needs `SourceRegistryStore` for `sync_connections_from_config`. No issue.

**Category:** docs-only (no issue)
**Fix:** None needed.

---

### F23: `wf_mcp.shared.names.py` still imports FastMCP at top level

**File:** `src/wf_mcp/shared/names.py:8-15`
**Content:** Imports `fastmcp.server.transforms` and `fastmcp.utilities.versions` at
module level for `ProxyNamespace`, `LdaNamespace`, and `ProxyToolName`.
**Status:** This is intentional -- `shared/names.py` is MCP frontend transport code
that belongs in a future `wf_transport_mcp`. The `RESERVED_CONNECTION_IDS` constant
has moved to `wf_sources_mcp.ids`, and `wf_mcp.shared.names` re-exports it.
The FastMCP import is only needed for the proxy namespace classes, which are
MCP-frontend-specific. No issue with extraction hygiene, but this is a
dependency boundary concern for future `wf_transport_mcp` extraction.

**Category:** future-work
**Fix:** Defer. Part of `wf_transport_mcp` extraction.

---

### F24: `wf_mcp.broker.service.source_catalog.py` docstring says "MCP-broker-internal"

**File:** `src/wf_mcp/broker/service/source_catalog.py:55-58`
**Content:** `"""Own service-local capability sources and catalog projections.\n\nThis is deliberately still MCP-broker-internal. It knows about stored MCP\ncatalog snapshots because hydrated workflow NodeSpecs must call back through\nthe broker's configured tool executor."""`
**Status:** Accurate. The source catalog service is broker-internal by design.
It manages `CapabilitySource` registrations and catalog hydration. The word
"still" implies future change, which is correct (eventually this may move
behind a protocol), but the docstring is honest about current state.

**Category:** docs-only (accurate)
**Fix:** None needed.

---

### F25: `wf_mcp.broker.service.upstream_transport.py` docstring says "not protocol-neutral"

**File:** `src/wf_mcp/broker/service/upstream_transport.py:48-50`
**Content:** `"""Own upstream MCP adapter/auth operations for the broker service.\n\nThis is not protocol-neutral. It is the MCP transport implementation used by\nadmin calls, discovery, generated workflow NodeSpecs, and live source checks."""`
**Status:** Accurate. This is broker-specific MCP transport orchestration.

**Category:** docs-only (accurate)
**Fix:** None needed.

---

## Stale Claims Summary

| Claim | Location | Status |
|-------|----------|--------|
| "parse_connection_id lives in wf_mcp.connections" | research doc | **Stale.** Canonical in `wf_sources_mcp.ids`. |
| "RESERVED_CONNECTION_IDS lives in wf_mcp.shared.names" | research doc | **Stale.** Canonical in `wf_sources_mcp.ids`. |
| "wf_mcp.runtime.factory imports ConnectionConfig at runtime" | research doc | **Stale.** Now a re-export shim. |
| "wf_mcp.sdk.adapter imports ConnectionConfig at runtime" | research doc | **Stale.** Now a re-export shim. |
| "during extraction" in workflow_surface shim docstrings | 5 files | **Stale.** Extraction is complete; shims are long-lived. |

## Items Safe to Fix Now

1. **F1:** Delete `src/wf_mcp/sdk/base.py` (dead re-export module)
2. **F3-F7:** Replace "during extraction" with "until callers migrate" in 5 workflow_surface shim docstrings
3. **F12:** Check and potentially remove `_model_from_schema` alias in `wf_mcp.workflow.wrappers`
4. **F19:** Update `WorkflowSurfaceHandlers` docstring to say "for legacy callers"

## Items to Defer

1. **F10, F11, F21:** Historical research doc is a snapshot; add a note at top
2. **F13:** Remove `CatalogSnapshot` re-export from `wf_mcp.models` when callers migrate
3. **F23:** FastMCP import in `shared/names.py` is part of future `wf_transport_mcp` extraction
4. All completed-plan references in historical docs

## Correctness Issues

None found. All compatibility shims correctly re-export from canonical locations.
The dependency direction is clean: `wf_sources_mcp` imports nothing from `wf_mcp`.

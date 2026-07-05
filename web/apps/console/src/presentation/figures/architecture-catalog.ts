import { defineFigureCatalog } from "./catalog.js";
import type { FigureCatalogDefinition } from "./model.js";

export const ARCHITECTURE_CATALOG_ID = "system-architecture";

export const architectureCatalog: FigureCatalogDefinition = defineFigureCatalog({
  rootFigureId: "architecture-overview",
  figures: [
    {
      id: "architecture-overview",
      title: "Architecture",
      layout: { kind: "layered" },
      nodes: [
        {
          id: "client-operations",
          label: "Client operations",
          summary: "Public lifecycle surface",
          kind: "actor",
          evidencePointer: "docs/source_architecture.md",
          childFigureId: "client-surface-detail",
        },
        {
          id: "application-lifecycle",
          label: "Application lifecycle",
          summary: "WorkflowApi + WorkflowServer",
          kind: "operation",
          evidencePointer: "src/wf_api/service.py",
        },
        {
          id: "runtime-providers",
          label: "Runtime & providers",
          summary: "CapabilitySource projection",
          kind: "runtime",
          evidencePointer: "src/wf_core/runtime/ops/state.py",
          childFigureId: "runtime-provider-detail",
        },
        {
          id: "node-use",
          label: "NodeUse",
          summary: "Typed node execution",
          kind: "operation",
          evidencePointer: "src/wf_core/runtime/ops/nodes.py",
          childFigureId: "node-use-detail",
        },
      ],
      edges: [
        { id: "e-client-lifecycle", from: "client-operations", to: "application-lifecycle", label: "calls" },
        { id: "e-lifecycle-runtime", from: "application-lifecycle", to: "runtime-providers", label: "delegates" },
        { id: "e-runtime-node", from: "runtime-providers", to: "node-use", label: "invokes" },
      ],
    },
    {
      id: "client-surface-detail",
      title: "Client surface",
      layout: { kind: "flow" },
      nodes: [
        {
          id: "cli",
          label: "CLI",
          summary: "wf command entry",
          kind: "actor",
          evidencePointer: "docs/project_map.md",
        },
        {
          id: "json-rpc",
          label: "JSON-RPC HTTP",
          summary: "wf_transport_rpc_http",
          kind: "actor",
          evidencePointer: "src/wf_transport_rpc_http/",
        },
        {
          id: "web-console",
          label: "Web console",
          summary: "React SPA",
          kind: "actor",
          evidencePointer: "web/apps/console",
        },
      ],
      edges: [
        { id: "e-cli-api", from: "cli", to: "json-rpc", label: "uses" },
        { id: "e-console-api", from: "web-console", to: "json-rpc", label: "uses" },
      ],
    },
    {
      id: "runtime-provider-detail",
      title: "Runtime and providers",
      layout: { kind: "layered" },
      nodes: [
        {
          id: "workflow-server",
          label: "WorkflowServer",
          summary: "wf_server composition",
          kind: "runtime",
          evidencePointer: "src/wf_server/context.py",
        },
        {
          id: "workflow-api",
          label: "WorkflowApi",
          summary: "Application operations",
          kind: "operation",
          evidencePointer: "src/wf_api/service.py",
        },
        {
          id: "capability-source",
          label: "CapabilitySource",
          summary: "Provider-neutral projection",
          kind: "artifact",
          evidencePointer: "docs/source_architecture.md",
        },
        {
          id: "configured-providers",
          label: "Configured providers",
          summary: "Source families",
          kind: "runtime",
          evidencePointer: "docs/source_architecture.md",
          childFigureId: "configured-provider-detail",
        },
        {
          id: "deterministic-kernel",
          label: "Deterministic kernel",
          summary: "Replay-safe execution",
          kind: "artifact",
          evidencePointer: "src/wf_core/runtime/step.py",
        },
      ],
      edges: [
        { id: "e-server-api", from: "workflow-server", to: "workflow-api", label: "exposes" },
        { id: "e-api-source", from: "workflow-api", to: "capability-source", label: "projects" },
        { id: "e-source-providers", from: "capability-source", to: "configured-providers", label: "loads" },
        { id: "e-providers-kernel", from: "configured-providers", to: "deterministic-kernel", label: "runs" },
      ],
    },
    {
      id: "configured-provider-detail",
      title: "Configured providers",
      layout: { kind: "layered" },
      nodes: [
        {
          id: "builtin-sources",
          label: "Built-in sources",
          summary: "wf.std / wf.recipes",
          kind: "runtime",
          evidencePointer: "src/wf_api/service.py",
        },
        {
          id: "mcp-sources",
          label: "MCP sources",
          summary: "wf_sources_mcp",
          kind: "runtime",
          evidencePointer: "src/wf_sources_mcp/",
        },
        {
          id: "python-sources",
          label: "Python sources",
          summary: "wf_sources_python",
          kind: "runtime",
          evidencePointer: "src/wf_sources_python/",
        },
        {
          id: "openapi-future",
          label: "OpenAPI sources",
          summary: "Future extension",
          kind: "boundary",
        },
      ],
      edges: [
        { id: "e-builtin-mcp", from: "builtin-sources", to: "mcp-sources", label: "adjacent" },
        { id: "e-mcp-python", from: "mcp-sources", to: "python-sources", label: "adjacent" },
        { id: "e-python-openapi", from: "python-sources", to: "openapi-future", label: "future" },
      ],
    },
    {
      id: "node-use-detail",
      title: "NodeUse execution",
      layout: { kind: "layered" },
      nodes: [
        {
          id: "resolve-bindings",
          label: "Resolve input bindings",
          summary: "NodeSpec inputs",
          kind: "operation",
          evidencePointer: "src/wf_core/runtime/ops/nodes.py",
        },
        {
          id: "invoke-handler",
          label: "Invoke handler",
          summary: "Capability call",
          kind: "operation",
          evidencePointer: "src/wf_core/runtime/step.py",
        },
        {
          id: "normalize-result",
          label: "Normalize NodeResult",
          summary: "Typed output",
          kind: "operation",
          evidencePointer: "src/wf_core/runtime/ops/nodes.py",
        },
        {
          id: "apply-reducers",
          label: "Apply output reducers",
          summary: "State mutations",
          kind: "operation",
          evidencePointer: "src/wf_core/runtime/ops/state.py",
        },
        {
          id: "route-outcome",
          label: "Route outcome",
          summary: "Success or failure path",
          kind: "operation",
          evidencePointer: "src/wf_core/runtime/step.py",
        },
        {
          id: "record-trace",
          label: "Record trace",
          summary: "Inspection evidence",
          kind: "evidence",
          evidencePointer: "src/wf_core/runtime/ops/nodes.py",
        },
      ],
      edges: [
        { id: "e-resolve-invoke", from: "resolve-bindings", to: "invoke-handler", label: "feeds" },
        { id: "e-invoke-normalize", from: "invoke-handler", to: "normalize-result", label: "produces" },
        { id: "e-normalize-reducers", from: "normalize-result", to: "apply-reducers", label: "reduces" },
        { id: "e-reducers-outcome", from: "apply-reducers", to: "route-outcome", label: "routes" },
        { id: "e-outcome-trace", from: "route-outcome", to: "record-trace", label: "records" },
      ],
    },
  ],
});

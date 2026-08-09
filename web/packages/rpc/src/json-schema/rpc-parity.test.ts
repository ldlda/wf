import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { Either, Schema } from "effect";
import { beforeAll, describe, expect, it } from "vitest";
import { WorkflowRpcs } from "../rpcs.js";
import { authoredRpcSchemas } from "./authored-rpc-fixtures.js";
import { translateJsonSchema } from "./translator.js";

const WorkflowHealthPayloadSchema =
  authoredRpcSchemas["workflow.health"].payload;
const WorkflowHealthResultSchema =
  authoredRpcSchemas["workflow.health"].success;
const WorkflowSourcesListPayloadSchema =
  authoredRpcSchemas["workflow.sources.list"].payload;
const WorkflowSourcesListResultSchema =
  authoredRpcSchemas["workflow.sources.list"].success;
const WorkflowCapabilitiesListPayloadSchema =
  authoredRpcSchemas["workflow.capabilities.list"].payload;
const WorkflowCapabilitiesListResultSchema =
  authoredRpcSchemas["workflow.capabilities.list"].success;
const WorkflowCapabilitiesInspectPayloadSchema =
  authoredRpcSchemas["workflow.capabilities.inspect"].payload;
const WorkflowCapabilitiesInspectResultSchema =
  authoredRpcSchemas["workflow.capabilities.inspect"].success;
const WorkflowDraftWorkspacesListPayloadSchema =
  authoredRpcSchemas["workflow.draft_workspaces.list"].payload;
const WorkflowDraftWorkspacesListResultSchema =
  authoredRpcSchemas["workflow.draft_workspaces.list"].success;
const WorkflowDraftWorkspacesGetPayloadSchema =
  authoredRpcSchemas["workflow.draft_workspaces.get"].payload;
const WorkflowDraftWorkspacesGetResultSchema =
  authoredRpcSchemas["workflow.draft_workspaces.get"].success;
const WorkflowDraftWorkspacesCreateEmptyPayloadSchema =
  authoredRpcSchemas["workflow.draft_workspaces.create_empty"].payload;
const WorkflowDraftWorkspacesCreateEmptyResultSchema =
  authoredRpcSchemas["workflow.draft_workspaces.create_empty"].success;
const WorkflowDraftWorkspacesCreateFromCapabilityPayloadSchema =
  authoredRpcSchemas["workflow.draft_workspaces.create_from_capability"].payload;
const WorkflowDraftWorkspacesCreateFromCapabilityResultSchema =
  authoredRpcSchemas["workflow.draft_workspaces.create_from_capability"].success;
const WorkflowDraftWorkspacesAddStepFromCapabilityPayloadSchema =
  authoredRpcSchemas["workflow.draft_workspaces.add_step_from_capability"].payload;
const WorkflowDraftWorkspacesAddStepFromCapabilityResultSchema =
  authoredRpcSchemas["workflow.draft_workspaces.add_step_from_capability"].success;
const WorkflowDraftWorkspacesUpdateCapabilityStepPayloadSchema =
  authoredRpcSchemas["workflow.draft_workspaces.update_capability_step"].payload;
const WorkflowDraftWorkspacesUpdateCapabilityStepResultSchema =
  authoredRpcSchemas["workflow.draft_workspaces.update_capability_step"].success;
const WorkflowDraftWorkspacesSetRoutePayloadSchema =
  authoredRpcSchemas["workflow.draft_workspaces.set_route"].payload;
const WorkflowDraftWorkspacesSetRouteResultSchema =
  authoredRpcSchemas["workflow.draft_workspaces.set_route"].success;
const WorkflowDraftWorkspacesSetStepInputBindingsPayloadSchema =
  authoredRpcSchemas["workflow.draft_workspaces.set_step_input_bindings"].payload;
const WorkflowDraftWorkspacesSetStepInputBindingsResultSchema =
  authoredRpcSchemas["workflow.draft_workspaces.set_step_input_bindings"].success;
const WorkflowDraftWorkspacesSetStepOutputBindingsPayloadSchema =
  authoredRpcSchemas["workflow.draft_workspaces.set_step_output_bindings"].payload;
const WorkflowDraftWorkspacesSetStepOutputBindingsResultSchema =
  authoredRpcSchemas["workflow.draft_workspaces.set_step_output_bindings"].success;
const WorkflowDraftWorkspacesValidatePayloadSchema =
  authoredRpcSchemas["workflow.draft_workspaces.validate"].payload;
const WorkflowDraftWorkspacesValidateResultSchema =
  authoredRpcSchemas["workflow.draft_workspaces.validate"].success;
const WorkflowArtifactsListPayloadSchema =
  authoredRpcSchemas["workflow.artifacts.list"].payload;
const WorkflowArtifactsListResultSchema =
  authoredRpcSchemas["workflow.artifacts.list"].success;
const WorkflowArtifactsInspectPayloadSchema =
  authoredRpcSchemas["workflow.artifacts.inspect"].payload;
const WorkflowArtifactsInspectResultSchema =
  authoredRpcSchemas["workflow.artifacts.inspect"].success;
const WorkflowDeploymentsListPayloadSchema =
  authoredRpcSchemas["workflow.deployments.list"].payload;
const WorkflowDeploymentsListResultSchema =
  authoredRpcSchemas["workflow.deployments.list"].success;
const WorkflowDeploymentsInspectPayloadSchema =
  authoredRpcSchemas["workflow.deployments.inspect"].payload;
const WorkflowDeploymentsInspectResultSchema =
  authoredRpcSchemas["workflow.deployments.inspect"].success;
const WorkflowDeploymentsValidatePayloadSchema =
  authoredRpcSchemas["workflow.deployments.validate"].payload;
const WorkflowDeploymentsValidateResultSchema =
  authoredRpcSchemas["workflow.deployments.validate"].success;
const WorkflowRunsListPayloadSchema =
  authoredRpcSchemas["workflow.runs.list"].payload;
const WorkflowRunsListResultSchema =
  authoredRpcSchemas["workflow.runs.list"].success;
const WorkflowRunsInspectPayloadSchema =
  authoredRpcSchemas["workflow.runs.inspect"].payload;
const WorkflowRunsInspectResultSchema =
  authoredRpcSchemas["workflow.runs.inspect"].success;
const WorkflowRunsStartPayloadSchema =
  authoredRpcSchemas["workflow.runs.start"].payload;
const WorkflowRunsStartResultSchema =
  authoredRpcSchemas["workflow.runs.start"].success;
const WorkflowRunsResumePayloadSchema =
  authoredRpcSchemas["workflow.runs.resume"].payload;
const WorkflowRunsResumeResultSchema =
  authoredRpcSchemas["workflow.runs.resume"].success;
const WorkflowRunsTracePayloadSchema =
  authoredRpcSchemas["workflow.runs.trace"].payload;
const WorkflowRunsTraceResultSchema =
  authoredRpcSchemas["workflow.runs.trace"].success;

const repositoryRoot = fileURLToPath(new URL("../../../../..", import.meta.url));
const decodeJson = Schema.decodeUnknownSync(Schema.parseJson(Schema.Unknown));

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

interface ParityCase {
  readonly method: string;
  readonly payload: Schema.Schema.AnyNoContext;
  readonly success: Schema.Schema.AnyNoContext;
  readonly validPayload: unknown;
  readonly validSuccess: unknown;
  readonly invalidPayload?: unknown;
  readonly invalidSuccess?: unknown;
  readonly manifestValidPayload?: unknown;
  readonly manifestValidSuccess?: unknown;
  readonly additionalSuccessSamples?: ReadonlyArray<{
    readonly label: string;
    readonly value: unknown;
    readonly authoredAccepts: boolean;
    readonly manifestAccepts: boolean;
  }>;
}

const nextActions = {
  can_continue: false,
  can_save_now: null,
  recommended_next_tool: null,
  reason: "run completed",
  patch_examples: [],
  warnings: [],
};

const interruptedRun = {
  run_id: "run_1",
  deployment_id: "report.default",
  artifact_id: "report",
  artifact_version: 1,
  status: "interrupted",
  resume_readiness: "ready",
  interrupt: { kind: "review", payload: {}, outcomes: [] },
  outcome: null,
  error: null,
  output: null,
  diagnostics: [],
  trace_count: 1,
  next_actions: nextActions,
};

// Keep both shapes: they expose the bidirectional compatibility gap without
// changing either the current authored decoder or the canonical manifest.
const manifestInterrupt = {
  id: "interrupt_1",
  frame_id: "frame_1",
  node_id: "review_issues",
  kind: "review",
  payload: {},
  resumable: true,
  route: null,
  outcomes: ["submitted", "cancelled"],
  request_schema: { type: "object" },
  resume_schema: { type: "object" },
  typed: true,
};

const manifestInterruptedRun = {
  ...interruptedRun,
  interrupt: manifestInterrupt,
};

const completedRun = {
  ...interruptedRun,
  status: "completed",
  resume_readiness: "not_applicable",
  interrupt: null,
  outcome: "completed",
  output: { report: "# Completed report" },
  trace_count: 4,
};

const authoredTraceFrame = {
  node_id: "review_issues",
  step_type: "interrupt",
  resolved_input: { report: "# Draft report" },
  outcome: "submitted",
  output: {},
  state_changes: {},
};

const manifestTraceFrame = {
  ...authoredTraceFrame,
  frame_id: "frame_1",
  next_node_id: "create_issues",
};

const draftWorkspace = {
  workspace_id: "console.demo",
  revision: 2,
  title: "Console demo",
  status: "valid",
  diagnostics: [],
  summary: {
    name: "console.demo",
    start: "echo",
    step_count: 1,
    route_count: 1,
    steps: ["echo"],
  },
  draft: {
    name: "console.demo",
    start: "echo",
    steps: { echo: { use: "local.example.echo" } },
    routes: { echo: { ok: "__end__" } },
  },
};

const createFromCapabilityResult = {
  ...draftWorkspace,
  next_actions: {
    can_continue: false,
    can_save_now: true,
    recommended_next_tool: "workflow.draft_workspaces.validate",
    reason: "draft is ready for validation",
    patch_examples: [],
    warnings: [],
  },
  wrapper_hints: {
    capability_name: "local.example.echo",
    confidence: "high",
    declared_outcomes: ["ok"],
    input_map: {},
    input_schema: { type: "object" },
    missing_decisions: [],
    notes: [],
    outcome_candidates: [],
    outcome_policy: "preserve_declared",
    output_map: {},
    output_schema: { type: "object" },
    state_schema: { type: "object" },
    suggested_wrapper_outcomes: ["ok"],
  },
};

const parityCases: ReadonlyArray<ParityCase> = [
  {
    method: "workflow.health",
    payload: WorkflowHealthPayloadSchema,
    success: WorkflowHealthResultSchema,
    validPayload: {},
    invalidPayload: { unexpected: true },
    validSuccess: { status: "ok", store_root: "C:/store" },
  },
  {
    method: "workflow.sources.list",
    payload: WorkflowSourcesListPayloadSchema,
    success: WorkflowSourcesListResultSchema,
    validPayload: { limit: 50 },
    validSuccess: { sources: [], next_cursor: null, total: 0 },
    invalidSuccess: {
      sources: [
        {
          id: "local.demo",
          kind: "python",
          enabled: true,
          description: null,
          tool_count: -1,
          node_spec_count: 0,
          reducer_count: 0,
          prompt_count: 0,
          resource_count: 0,
        },
      ],
      next_cursor: null,
      total: 1,
    },
  },
  {
    method: "workflow.capabilities.list",
    payload: WorkflowCapabilitiesListPayloadSchema,
    success: WorkflowCapabilitiesListResultSchema,
    validPayload: { query: "document", source_id: "local.lda_docs", limit: 25 },
    invalidPayload: { limit: 0 },
    validSuccess: {
      capabilities: [
        {
          kind: "node_spec",
          name: "local.lda_docs.read_documents",
          source_id: "local.lda_docs",
          description: "Read selected project documents.",
          outcomes: ["ok", "error"],
          is_async: false,
          input_fields: ["names"],
          output_fields: ["documents"],
        },
      ],
      next_cursor: null,
      total: 1,
    },
    invalidSuccess: {
      capabilities: [
        {
          kind: "node_spec",
          name: "local.lda_docs.read_documents",
          source_id: "local.lda_docs",
          description: null,
          outcomes: ["ok"],
          is_async: false,
          input_fields: [1],
          output_fields: ["documents"],
        },
      ],
      next_cursor: null,
      total: 1,
    },
  },
  {
    method: "workflow.capabilities.inspect",
    payload: WorkflowCapabilitiesInspectPayloadSchema,
    success: WorkflowCapabilitiesInspectResultSchema,
    validPayload: { qualified_name: "local.lda_docs.read_documents" },
    invalidPayload: { qualified_name: "" },
    validSuccess: {
      kind: "node_spec",
      name: "local.lda_docs.read_documents",
      source_id: "local.lda_docs",
      description: "Read selected project documents.",
      is_async: false,
      accepts_context: false,
      outcomes: ["ok", "error"],
      input_schema: { type: "object" },
      output_schema: { type: "object" },
      wrapper_hints: {
        capability_name: "local.lda_docs.read_documents",
        confidence: "high",
        declared_outcomes: ["ok", "error"],
        input_map: {},
        input_schema: { type: "object" },
        missing_decisions: [],
        notes: [],
        outcome_candidates: [],
        outcome_policy: "preserve_declared",
        output_map: {},
        output_schema: { type: "object" },
        state_schema: { type: "object" },
        suggested_wrapper_outcomes: ["ok", "error"],
      },
    },
    invalidSuccess: {
      kind: "node_spec",
      name: "local.lda_docs.read_documents",
      source_id: "local.lda_docs",
      description: null,
      is_async: false,
      accepts_context: false,
      outcomes: ["ok"],
      input_schema: { type: "object" },
      output_schema: { type: "object" },
    },
  },
  {
    method: "workflow.draft_workspaces.list",
    payload: WorkflowDraftWorkspacesListPayloadSchema,
    success: WorkflowDraftWorkspacesListResultSchema,
    validPayload: {},
    invalidPayload: { unexpected: true },
    validSuccess: {
      workspaces: [
        {
          workspace_id: "console.demo",
          revision: 1,
          title: "Console demo",
          status: "valid",
          diagnostics: [],
          summary: {
            name: "console.demo",
            start: "read",
            step_count: 1,
            route_count: 1,
            steps: ["read"],
          },
        },
      ],
    },
    invalidSuccess: {
      workspaces: [
        {
          workspace_id: "console.demo",
          revision: 1,
          title: "Console demo",
          status: "valid",
          diagnostics: [],
          summary: {
            name: "console.demo",
            start: "read",
            step_count: 1,
            route_count: 1,
            steps: [1],
          },
        },
      ],
    },
  },
  {
    method: "workflow.draft_workspaces.get",
    payload: WorkflowDraftWorkspacesGetPayloadSchema,
    success: WorkflowDraftWorkspacesGetResultSchema,
    validPayload: { workspace_id: "console.demo", include_draft: true },
    invalidPayload: { include_draft: true },
    validSuccess: {
      workspace_id: "console.demo",
      revision: 1,
      title: "Console demo",
      status: "valid",
      diagnostics: [],
      summary: {
        name: "console.demo",
        start: "read",
        step_count: 1,
        route_count: 1,
        steps: ["read"],
      },
      draft: {
        name: "console.demo",
        start: "read",
        steps: { read: { use: "local.lda_docs.read_documents" } },
        routes: { read: { ok: "__end__" } },
      },
    },
    invalidSuccess: {
      workspace_id: "console.demo",
      revision: 1,
      title: "Console demo",
      status: "valid",
      diagnostics: [],
      summary: {
        name: "console.demo",
        start: "read",
        step_count: 1,
        route_count: 1,
        steps: ["read"],
      },
      draft: null,
    },
  },
  {
    method: "workflow.draft_workspaces.create_empty",
    payload: WorkflowDraftWorkspacesCreateEmptyPayloadSchema,
    success: WorkflowDraftWorkspacesCreateEmptyResultSchema,
    validPayload: {
      workspace_id: "console.demo",
      name: "console.demo",
      title: "Console demo",
      input_schema: { type: "object" },
      state_schema: { type: "object" },
      output_schema: { type: "object" },
      outcomes: ["ok"],
    },
    invalidPayload: { workspace_id: "console.demo" },
    validSuccess: draftWorkspace,
    invalidSuccess: {
      ...draftWorkspace,
      summary: { ...draftWorkspace.summary, steps: [1] },
    },
  },
  {
    method: "workflow.draft_workspaces.create_from_capability",
    payload: WorkflowDraftWorkspacesCreateFromCapabilityPayloadSchema,
    success: WorkflowDraftWorkspacesCreateFromCapabilityResultSchema,
    validPayload: {
      workspace_id: "console.demo",
      capability_name: "local.example.echo",
      name: "console.demo",
      title: "Console demo",
      input_schema: { type: "object" },
      state_schema: { type: "object" },
      output_schema: { type: "object" },
      input: [{ text: "hello" }],
      output: [{ text: "state.text" }],
      input_map: { "input.text": "text" },
      output_map: { text: "state.text" },
      error_message_source: "state.error_message",
    },
    invalidPayload: { workspace_id: "console.demo" },
    validSuccess: createFromCapabilityResult,
    invalidSuccess: {
      ...createFromCapabilityResult,
      summary: { ...createFromCapabilityResult.summary, steps: [1] },
    },
  },
  {
    method: "workflow.draft_workspaces.add_step_from_capability",
    payload: WorkflowDraftWorkspacesAddStepFromCapabilityPayloadSchema,
    success: WorkflowDraftWorkspacesAddStepFromCapabilityResultSchema,
    validPayload: {
      workspace_id: "console.demo",
      revision: 1,
      step_id: "echo",
      capability_name: "local.example.echo",
      route_from_step: null,
      route_from_outcome: "ok",
      routes: { ok: "__end__" },
      input_map: { "input.text": "text" },
      input_bindings: [
        { path: "input.text", target: "text" },
        { target: "format", value: { value: "plain" } },
      ],
      bind_outputs: { text: "state.text" },
      desc: "Echo text",
      retry: 1,
      timeout_seconds: 30,
    },
    invalidPayload: {
      workspace_id: "console.demo",
      revision: 0,
      step_id: "echo",
      capability_name: "local.example.echo",
    },
    validSuccess: draftWorkspace,
    invalidSuccess: {
      ...draftWorkspace,
      summary: { ...draftWorkspace.summary, steps: [1] },
    },
  },
  {
    method: "workflow.draft_workspaces.update_capability_step",
    payload: WorkflowDraftWorkspacesUpdateCapabilityStepPayloadSchema,
    success: WorkflowDraftWorkspacesUpdateCapabilityStepResultSchema,
    validPayload: {
      workspace_id: "console.demo",
      revision: 2,
      step_id: "echo",
      update: {
        desc: "Echo text",
        input: [{ path: "input.text", target: "text" }],
        retry: 2,
        timeout_seconds: 45,
      },
    },
    invalidPayload: {
      workspace_id: "console.demo",
      revision: 2,
      step_id: "echo",
      update: { retry: -1 },
    },
    validSuccess: draftWorkspace,
    invalidSuccess: {
      ...draftWorkspace,
      summary: { ...draftWorkspace.summary, steps: [1] },
    },
  },
  {
    method: "workflow.draft_workspaces.set_route",
    payload: WorkflowDraftWorkspacesSetRoutePayloadSchema,
    success: WorkflowDraftWorkspacesSetRouteResultSchema,
    validPayload: {
      workspace_id: "console.demo",
      revision: 2,
      step_id: "echo",
      outcome: "ok",
      target: "__end__",
    },
    invalidPayload: {
      workspace_id: "console.demo",
      revision: 2,
      step_id: "echo",
      outcome: "ok",
      target: "",
    },
    validSuccess: draftWorkspace,
    invalidSuccess: {
      ...draftWorkspace,
      summary: { ...draftWorkspace.summary, steps: [1] },
    },
  },
  {
    method: "workflow.draft_workspaces.set_step_input_bindings",
    payload: WorkflowDraftWorkspacesSetStepInputBindingsPayloadSchema,
    success: WorkflowDraftWorkspacesSetStepInputBindingsResultSchema,
    validPayload: {
      workspace_id: "console.demo",
      revision: 3,
      step_id: "render",
      bindings: [
        { path: "input.title", target: "report.title" },
        { target: "format", value: "markdown" },
        { target: "nullable", value: null },
        { target: "tags", value: ["draft", 2, false] },
        { target: "options", value: { strict: true } },
      ],
    },
    invalidPayload: {
      workspace_id: "console.demo",
      revision: 3,
      step_id: "render",
      bindings: [{ path: "input.title", target: "report.title", value: "bad" }],
    },
    validSuccess: draftWorkspace,
    invalidSuccess: {
      ...draftWorkspace,
      summary: { ...draftWorkspace.summary, steps: [1] },
    },
  },
  {
    method: "workflow.draft_workspaces.set_step_output_bindings",
    payload: WorkflowDraftWorkspacesSetStepOutputBindingsPayloadSchema,
    success: WorkflowDraftWorkspacesSetStepOutputBindingsResultSchema,
    validPayload: {
      workspace_id: "console.demo",
      revision: 4,
      step_id: "render",
      bindings: [{ source: "report", target: "state.report" }],
    },
    invalidPayload: {
      workspace_id: "console.demo",
      revision: 4,
      step_id: "render",
      bindings: [{ source: "report", target: { root: "state", parts: [] } }],
    },
    validSuccess: draftWorkspace,
    invalidSuccess: {
      ...draftWorkspace,
      summary: { ...draftWorkspace.summary, steps: [1] },
    },
  },
  {
    method: "workflow.draft_workspaces.validate",
    payload: WorkflowDraftWorkspacesValidatePayloadSchema,
    success: WorkflowDraftWorkspacesValidateResultSchema,
    validPayload: { workspace_id: "console.demo" },
    invalidPayload: {},
    validSuccess: draftWorkspace,
    invalidSuccess: {
      ...draftWorkspace,
      summary: { ...draftWorkspace.summary, steps: [1] },
    },
  },
  {
    method: "workflow.artifacts.list",
    payload: WorkflowArtifactsListPayloadSchema,
    success: WorkflowArtifactsListResultSchema,
    validPayload: { limit: 50 },
    validSuccess: {
      nodes: [],
      total: 0,
      cursor: null,
      next_cursor: null,
      limit: 50,
    },
  },
  {
    method: "workflow.artifacts.inspect",
    payload: WorkflowArtifactsInspectPayloadSchema,
    success: WorkflowArtifactsInspectResultSchema,
    validPayload: { artifact_id: "report", version: 1 },
    invalidPayload: { artifact_id: "report", version: 0 },
    validSuccess: {
      id: "report",
      version: 1,
      title: "Report",
      kind: "workflow",
      description: null,
      outcomes: ["ok"],
      input_schema: { type: "object" },
      output_schema: { type: "object" },
      plan: { nodes: [], edges: [] },
      required_capabilities: [],
      workflow_dependencies: {},
      created_from_catalog_version: null,
    },
  },
  {
    method: "workflow.deployments.list",
    payload: WorkflowDeploymentsListPayloadSchema,
    success: WorkflowDeploymentsListResultSchema,
    validPayload: {},
    invalidPayload: { unexpected: true },
    validSuccess: { deployments: [] },
  },
  {
    method: "workflow.deployments.inspect",
    payload: WorkflowDeploymentsInspectPayloadSchema,
    success: WorkflowDeploymentsInspectResultSchema,
    validPayload: { deployment_id: "report.default" },
    validSuccess: {
      id: "report.default",
      artifact_id: "report",
      artifact_version: 1,
      bindings: [
        { logical_source: "local.report", concrete_source: "report" },
      ],
      drift_policy: "block",
    },
  },
  {
    method: "workflow.deployments.validate",
    payload: WorkflowDeploymentsValidatePayloadSchema,
    success: WorkflowDeploymentsValidateResultSchema,
    validPayload: { deployment_id: "report.default" },
    validSuccess: {
      deployment_id: "report.default",
      artifact_id: "report",
      artifact_version: 1,
      status: "runnable",
      diagnostics: [],
      next_actions: nextActions,
    },
  },
  {
    method: "workflow.runs.list",
    payload: WorkflowRunsListPayloadSchema,
    success: WorkflowRunsListResultSchema,
    validPayload: { limit: 50 },
    validSuccess: {
      runs: [],
      total: 0,
      cursor: null,
      next_cursor: null,
      limit: 50,
    },
  },
  {
    method: "workflow.runs.inspect",
    payload: WorkflowRunsInspectPayloadSchema,
    success: WorkflowRunsInspectResultSchema,
    validPayload: { run_id: "run_1" },
    validSuccess: interruptedRun,
    manifestValidSuccess: manifestInterruptedRun,
  },
  {
    method: "workflow.runs.start",
    payload: WorkflowRunsStartPayloadSchema,
    success: WorkflowRunsStartResultSchema,
    validPayload: {
      deployment_id: "report.default",
      workflow_input: { documents: ["brief.md"] },
      trace_range: { start: 0, limit: 50 },
    },
    validSuccess: interruptedRun,
    manifestValidSuccess: manifestInterruptedRun,
  },
  {
    method: "workflow.runs.resume",
    payload: WorkflowRunsResumePayloadSchema,
    success: WorkflowRunsResumeResultSchema,
    validPayload: {
      run_id: "run_1",
      resume_payload: { approved: true },
      resume_outcome: "submitted",
      trace_range: { start: 0, limit: 50 },
    },
    validSuccess: completedRun,
    additionalSuccessSamples: [
      {
        label: "authored-reduced-interrupt",
        value: interruptedRun,
        authoredAccepts: true,
        manifestAccepts: false,
      },
      {
        label: "manifest-complete-interrupt",
        value: manifestInterruptedRun,
        authoredAccepts: false,
        manifestAccepts: true,
      },
    ],
  },
  {
    method: "workflow.runs.trace",
    payload: WorkflowRunsTracePayloadSchema,
    success: WorkflowRunsTraceResultSchema,
    validPayload: { run_id: "run_1", trace_range: { start: 0, limit: 50 } },
    validSuccess: {
      run_id: "run_1",
      status: "interrupted",
      trace: [authoredTraceFrame],
      trace_start: 0,
      trace_limit: 50,
      trace_truncated: false,
    },
    manifestValidSuccess: {
      ...manifestInterruptedRun,
      trace: [manifestTraceFrame],
      trace_start: 0,
      trace_limit: 50,
      trace_truncated: false,
    },
  },
];

let manifest: Record<string, unknown>;
let components: Readonly<Record<string, unknown>>;

beforeAll(async () => {
  const text = await readFile(
    `${repositoryRoot}/contracts/workflow-api.manifest.json`,
    "utf8",
  );
  const decoded = decodeJson(text);
  if (!isRecord(decoded) || !isRecord(decoded.components)) {
    throw new Error("invalid checked workflow contract manifest");
  }
  const schemas = decoded.components.schemas;
  if (!isRecord(schemas)) throw new Error("invalid manifest component schemas");
  manifest = decoded;
  components = schemas;
});

const operationFor = (method: string): Record<string, unknown> => {
  const operations = manifest.operations;
  if (!Array.isArray(operations)) throw new Error("manifest operations are invalid");
  const operation = operations.find(
    (candidate) => isRecord(candidate) && candidate.method === method,
  );
  if (!isRecord(operation)) throw new Error(`missing manifest operation ${method}`);
  return operation;
};

const payloadJsonSchema = (operation: Record<string, unknown>): unknown => {
  if (!Array.isArray(operation.params)) {
    throw new Error(`invalid params for ${String(operation.method)}`);
  }
  const properties: Array<[string, unknown]> = [];
  const required: string[] = [];
  for (const parameter of operation.params) {
    if (
      !isRecord(parameter) ||
      typeof parameter.name !== "string" ||
      !("schema" in parameter)
    ) {
      throw new Error(`invalid parameter for ${String(operation.method)}`);
    }
    properties.push([parameter.name, parameter.schema]);
    if (parameter.required === true) required.push(parameter.name);
  }
  return {
    additionalProperties: false,
    properties: Object.fromEntries(properties),
    required,
    type: "object",
  };
};

const successJsonSchema = (operation: Record<string, unknown>): unknown => {
  if (!isRecord(operation.result) || !("schema" in operation.result)) {
    throw new Error(`invalid result for ${String(operation.method)}`);
  }
  return operation.result.schema;
};

const accepts = (schema: Schema.Schema.AnyNoContext, value: unknown): boolean =>
  Either.isRight(
    Schema.decodeUnknownEither(schema)(value, { onExcessProperty: "error" }),
  );

interface ParityReport {
  readonly blockers: ReadonlyArray<string>;
  readonly mismatches: ReadonlyArray<string>;
}

const compareSide = (
  testCase: ParityCase,
  side: "payload" | "success",
  authored: Schema.Schema.AnyNoContext,
  jsonSchema: unknown,
  valid: unknown,
  invalid: unknown,
  manifestValid: unknown | undefined,
  additionalSamples: ParityCase["additionalSuccessSamples"],
  blockers: string[],
  mismatches: string[],
): void => {
  expect(accepts(authored, valid), `${testCase.method} authored ${side}`).toBe(
    true,
  );
  expect(
    accepts(authored, invalid),
    `${testCase.method} authored invalid ${side}`,
  ).toBe(false);

  const translated = translateJsonSchema(jsonSchema, { components });
  if (Either.isLeft(translated)) {
    blockers.push(
      `${testCase.method}:${side}:${translated.left.keyword ?? "schema"}` +
        `@${translated.left.path}`,
    );
    return;
  }
  for (const [label, sample] of [
    ["authored-valid", valid],
    ["authored-invalid", invalid],
  ] as const) {
    if (accepts(authored, sample) !== accepts(translated.right, sample)) {
      mismatches.push(`${testCase.method}:${side}:${label}`);
    }
  }
  if (manifestValid !== undefined) {
    expect(
      accepts(translated.right, manifestValid),
      `${testCase.method} manifest-valid ${side}`,
    ).toBe(true);
    if (
      accepts(authored, manifestValid) !==
      accepts(translated.right, manifestValid)
    ) {
      mismatches.push(`${testCase.method}:${side}:manifest-valid`);
    }
  }
  for (const sample of additionalSamples ?? []) {
    expect(accepts(authored, sample.value), `${sample.label} authored`).toBe(
      sample.authoredAccepts,
    );
    expect(
      accepts(translated.right, sample.value),
      `${sample.label} manifest`,
    ).toBe(sample.manifestAccepts);
    if (sample.authoredAccepts !== sample.manifestAccepts) {
      mismatches.push(`${testCase.method}:${side}:${sample.label}`);
    }
  }
};

const parityReport = (): ParityReport => {
  const blockers: string[] = [];
  const mismatches: string[] = [];
  for (const testCase of parityCases) {
    const operation = operationFor(testCase.method);
    compareSide(
      testCase,
      "payload",
      testCase.payload,
      payloadJsonSchema(operation),
      testCase.validPayload,
      testCase.invalidPayload ?? null,
      testCase.manifestValidPayload,
      undefined,
      blockers,
      mismatches,
    );
    compareSide(
      testCase,
      "success",
      testCase.success,
      successJsonSchema(operation),
      testCase.validSuccess,
      testCase.invalidSuccess ?? null,
      testCase.manifestValidSuccess,
      testCase.additionalSuccessSamples,
      blockers,
      mismatches,
    );
  }
  return { blockers, mismatches };
};

describe("authored RPC and manifest schema parity", () => {
  it("catalogs every authored RPC exactly once", () => {
    const expectedMethods = [
      "workflow.health",
      "workflow.sources.list",
      "workflow.capabilities.list",
      "workflow.capabilities.inspect",
      "workflow.draft_workspaces.list",
      "workflow.draft_workspaces.get",
      "workflow.draft_workspaces.create_empty",
      "workflow.draft_workspaces.create_from_capability",
      "workflow.draft_workspaces.add_step_from_capability",
      "workflow.draft_workspaces.update_capability_step",
      "workflow.draft_workspaces.set_route",
      "workflow.draft_workspaces.set_step_input_bindings",
      "workflow.draft_workspaces.set_step_output_bindings",
      "workflow.draft_workspaces.validate",
      "workflow.artifacts.list",
      "workflow.artifacts.inspect",
      "workflow.deployments.list",
      "workflow.deployments.inspect",
      "workflow.deployments.validate",
      "workflow.runs.list",
      "workflow.runs.inspect",
      "workflow.runs.start",
      "workflow.runs.resume",
      "workflow.runs.trace",
    ];
    expect(parityCases.map(({ method }) => method)).toEqual(expectedMethods);
    expect(Array.from(WorkflowRpcs.requests.keys())).toEqual(expectedMethods);
  });

  it("reports the exact catalogued authored decoder mismatches", () => {
    expect(parityReport().mismatches).toEqual([
      "workflow.runs.inspect:success:authored-valid",
      "workflow.runs.inspect:success:manifest-valid",
      "workflow.runs.start:success:authored-valid",
      "workflow.runs.start:success:manifest-valid",
      "workflow.runs.resume:success:authored-reduced-interrupt",
      "workflow.runs.resume:success:manifest-complete-interrupt",
      "workflow.runs.trace:success:authored-valid",
      "workflow.runs.trace:success:manifest-valid",
    ]);
  });

  it("reports the exact remaining translator blockers", () => {
    expect(parityReport().blockers).toEqual([
      "workflow.draft_workspaces.add_step_from_capability:payload:oneOf@#/components/schemas/InputPathBinding.properties.path",
      "workflow.draft_workspaces.update_capability_step:payload:oneOf@#/components/schemas/InputPathBinding.properties.path",
      "workflow.draft_workspaces.set_step_input_bindings:payload:oneOf@#/components/schemas/InputPathBinding.properties.path",
      "workflow.draft_workspaces.set_step_output_bindings:payload:oneOf@#/components/schemas/OutputBinding.properties.source",
    ]);
  });
});

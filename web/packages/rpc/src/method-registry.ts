import { Schema } from "effect";
import type {
  NodeSpecCapabilitySummary,
  WorkflowOperationName,
  WrapperArtifactCapabilitySummary,
} from "./generated/workflow-contract.js";
import {
  WorkflowHealthResultSchema,
  WorkflowSourcesListPayloadSchema,
  WorkflowSourcesListResultSchema,
  WorkflowCapabilitiesListPayloadSchema,
  WorkflowCapabilitiesListResultSchema,
  WorkflowCapabilitiesInspectPayloadSchema,
  WorkflowCapabilitiesInspectResultSchema,
  WorkflowDraftWorkspacesListResultSchema,
  WorkflowDraftWorkspacesGetPayloadSchema,
  WorkflowDraftWorkspacesGetResultSchema,
  WorkflowArtifactsListPayloadSchema,
  WorkflowArtifactsListResultSchema,
  WorkflowArtifactsInspectPayloadSchema,
  WorkflowArtifactsInspectResultSchema,
  WorkflowDeploymentsListResultSchema,
  WorkflowDeploymentsInspectPayloadSchema,
  WorkflowDeploymentsInspectResultSchema,
  WorkflowDeploymentsValidatePayloadSchema,
  WorkflowDeploymentsValidateResultSchema,
  WorkflowRunsListPayloadSchema,
  WorkflowRunsListResultSchema,
  WorkflowRunsInspectPayloadSchema,
  WorkflowRunsInspectResultSchema,
  WorkflowRunsStartPayloadSchema,
  WorkflowRunsStartResultSchema,
  WorkflowRunsResumePayloadSchema,
  WorkflowRunsResumeResultSchema,
  WorkflowRunsTracePayloadSchema,
  WorkflowRunsTraceResultSchema,
} from "./rpcs.js";

export type OperationMeta = {
  readonly method: WorkflowOperationName;
  readonly label: string;
  readonly explanation: string;
  readonly idempotency: "read" | "write";
  readonly equivalentCli: (params: unknown) => string;
  readonly interpret: (result: unknown) => unknown;
};

export type WorkflowHealthInterpreted = {
  readonly status: "ok";
  readonly storeRoot: string;
};

export type WorkflowSourcesListInterpreted = {
  readonly sources: ReadonlyArray<{
    readonly id: string;
    readonly kind: string;
    readonly enabled: boolean;
    readonly description: string | null;
    readonly counts: {
      readonly tools: number;
      readonly nodeSpecs: number;
      readonly reducers: number;
      readonly prompts: number;
      readonly resources: number;
    };
  }>;
  readonly nextCursor: string | null;
  readonly total: number;
};

export type CapabilitySummaryInterpreted = {
  readonly kind: "node_spec" | "wrapper_artifact";
  readonly name: string;
  readonly sourceId: string;
  readonly description: string | null;
  readonly outcomes: ReadonlyArray<string>;
  readonly isAsync: boolean;
  readonly inputFields: ReadonlyArray<string>;
  readonly outputFields: ReadonlyArray<string>;
  readonly artifactId?: string;
  readonly version?: number;
  readonly title?: string;
};

export type DraftWorkspaceInterpreted = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly title: string | null;
  readonly status: "valid" | "invalid" | "conflict";
  readonly diagnostics: ReadonlyArray<{
    readonly code: string;
    readonly path: string;
    readonly message: string;
    readonly stepId: string | null;
    readonly repairHint: string | null;
    readonly details: Readonly<Record<string, unknown>>;
  }>;
  readonly summary: {
    readonly name: unknown;
    readonly start: unknown;
    readonly stepCount: number;
    readonly routeCount: number;
    readonly steps: ReadonlyArray<string>;
  };
  readonly draft: Readonly<Record<string, unknown>> | null;
};

const interpretNextActions = (nextActions: {
  readonly can_continue: boolean;
  readonly can_save_now: boolean | null;
  readonly recommended_next_tool: string | null;
  readonly reason: string;
  readonly patch_examples: ReadonlyArray<unknown>;
  readonly warnings: ReadonlyArray<string>;
}) => ({
  canContinue: nextActions.can_continue,
  canSaveNow: nextActions.can_save_now,
  recommendedNextTool: nextActions.recommended_next_tool,
  reason: nextActions.reason,
  patchExamples: nextActions.patch_examples,
  warnings: nextActions.warnings,
});

const shellArg = (value: string | number): string => {
  const text = String(value);
  return /^[A-Za-z0-9._/@:-]+$/.test(text) ? text : `'${text.replace(/'/g, "''")}'`;
};

const interpretCapabilitySummary = (
  capability: NodeSpecCapabilitySummary | WrapperArtifactCapabilitySummary,
): CapabilitySummaryInterpreted => {
  const interpreted = {
    kind: capability.kind,
    name: capability.name,
    sourceId: capability.source_id,
    description: capability.description,
    outcomes: capability.outcomes,
    isAsync: capability.is_async,
    inputFields: capability.input_fields,
    outputFields: capability.output_fields,
  };
  if (capability.kind === "wrapper_artifact") {
    return {
      ...interpreted,
      artifactId: capability.artifact_id,
      version: capability.version,
      title: capability.title,
    };
  }
  return interpreted;
};

const interpretDraftWorkspace = (decoded: {
  readonly diagnostics: ReadonlyArray<{
    readonly code: string;
    readonly details?: Record<string, unknown>;
    readonly message: string;
    readonly path: string;
    readonly repair_hint?: string | null;
    readonly step_id?: string | null;
  }>;
  readonly draft?: Record<string, unknown>;
  readonly revision: number;
  readonly status: "valid" | "invalid" | "conflict";
  readonly summary: {
    readonly name: unknown;
    readonly route_count: number;
    readonly start: unknown;
    readonly step_count: number;
    readonly steps: ReadonlyArray<string>;
  };
  readonly title: string | null;
  readonly workspace_id: string;
}): DraftWorkspaceInterpreted => ({
  workspaceId: decoded.workspace_id,
  revision: decoded.revision,
  title: decoded.title,
  status: decoded.status,
  diagnostics: decoded.diagnostics.map((diagnostic) => ({
    code: diagnostic.code,
    path: diagnostic.path,
    message: diagnostic.message,
    stepId: diagnostic.step_id ?? null,
    repairHint: diagnostic.repair_hint ?? null,
    details: diagnostic.details ?? {},
  })),
  summary: {
    name: decoded.summary.name,
    start: decoded.summary.start,
    stepCount: decoded.summary.step_count,
    routeCount: decoded.summary.route_count,
    steps: decoded.summary.steps,
  },
  draft: decoded.draft ?? null,
});

/** Adapts a snake_case run detail from the server into camelCase for the browser. */
const interpretRunDetail = (decoded: {
  readonly run_id: string | null;
  readonly deployment_id: string;
  readonly artifact_id: string;
  readonly artifact_version: number;
  readonly status: string;
  readonly resume_readiness: string | null;
  readonly interrupt: unknown;
  readonly outcome: string | null;
  readonly error: string | null;
  readonly output: Record<string, unknown> | null;
  readonly diagnostics: ReadonlyArray<unknown>;
  readonly trace_count: number;
  readonly next_actions: Parameters<typeof interpretNextActions>[0];
}) => ({
  runId: decoded.run_id,
  deploymentId: decoded.deployment_id,
  artifactId: decoded.artifact_id,
  artifactVersion: decoded.artifact_version,
  status: decoded.status,
  resumeReadiness: decoded.resume_readiness,
  interrupt: decoded.interrupt,
  outcome: decoded.outcome,
  error: decoded.error,
  output: decoded.output,
  diagnostics: decoded.diagnostics,
  traceCount: decoded.trace_count,
  nextActions: interpretNextActions(decoded.next_actions),
});

const defineOperationEntries = <
  const Entries extends ReadonlyArray<OperationMeta>,
>(entries: Entries): Entries => entries;

const operationEntries = defineOperationEntries([
  {
    method: "workflow.health",
    label: "Health check",
    explanation: "Check if the workflow server is running",
    idempotency: "read",
    equivalentCli: () => "uv run wf status",
    interpret: (result): WorkflowHealthInterpreted => {
      const decoded = Schema.decodeUnknownSync(WorkflowHealthResultSchema)(result);
      return { status: decoded.status, storeRoot: decoded.store_root };
    },
  },
  {
    method: "workflow.sources.list",
    label: "List sources",
    explanation: "List registered data sources with pagination",
    idempotency: "read",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(WorkflowSourcesListPayloadSchema)(
        params,
        { onExcessProperty: "error" },
      );
      const parts = ["uv run wf source list"];
      if (p.limit != null) parts.push(`--limit ${p.limit}`);
      if (p.cursor != null) parts.push(`--cursor ${shellArg(p.cursor)}`);
      return parts.join(" ");
    },
    interpret: (result): WorkflowSourcesListInterpreted => {
      const decoded = Schema.decodeUnknownSync(
        WorkflowSourcesListResultSchema,
      )(result);
      return {
        sources: decoded.sources.map((source) => ({
          id: source.id,
          kind: source.kind,
          enabled: source.enabled,
          description: source.description,
          counts: {
            tools: source.tool_count,
            nodeSpecs: source.node_spec_count,
            reducers: source.reducer_count,
            prompts: source.prompt_count,
            resources: source.resource_count,
          },
        })),
        nextCursor: decoded.next_cursor,
        total: decoded.total,
      };
    },
  },
  {
    method: "workflow.capabilities.list",
    label: "List capabilities",
    explanation: "List workflow-authorable capabilities with pagination",
    idempotency: "read",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(WorkflowCapabilitiesListPayloadSchema)(
        params,
        { onExcessProperty: "error" },
      );
      const parts = ["uv run wf cap list"];
      if (p.query != null) parts.push(`--query ${shellArg(p.query)}`);
      if (p.source_id != null) parts.push(`--source ${shellArg(p.source_id)}`);
      if (p.cursor != null) parts.push(`--cursor ${shellArg(p.cursor)}`);
      if (p.limit != null) parts.push(`--limit ${p.limit}`);
      return parts.join(" ");
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(
        WorkflowCapabilitiesListResultSchema,
      )(result);
      return {
        capabilities: decoded.capabilities.map(interpretCapabilitySummary),
        nextCursor: decoded.next_cursor,
        total: decoded.total,
      };
    },
  },
  {
    method: "workflow.capabilities.inspect",
    label: "Inspect capability",
    explanation: "Inspect one workflow-authorable capability",
    idempotency: "read",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(
        WorkflowCapabilitiesInspectPayloadSchema,
      )(params, { onExcessProperty: "error" });
      return `uv run wf cap inspect ${shellArg(p.qualified_name)}`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(
        WorkflowCapabilitiesInspectResultSchema,
      )(result);
      const base = {
        kind: decoded.kind,
        name: decoded.name,
        sourceId: decoded.source_id,
        description: decoded.description,
        isAsync: decoded.is_async,
        outcomes: decoded.outcomes,
        inputSchema: decoded.input_schema,
        outputSchema: decoded.output_schema,
        wrapperHints: decoded.wrapper_hints,
      };
      if (decoded.kind === "wrapper_artifact") {
        return {
          ...base,
          artifactId: decoded.artifact_id,
          title: decoded.title,
          version: decoded.version,
          requiredCapabilities: decoded.required_capabilities,
        };
      }
      return {
        ...base,
        acceptsContext: decoded.accepts_context,
      };
    },
  },
  {
    method: "workflow.draft_workspaces.list",
    label: "List draft workspaces",
    explanation: "List persisted workflow draft workspaces",
    idempotency: "read",
    equivalentCli: () => "uv run wf draft list",
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(
        WorkflowDraftWorkspacesListResultSchema,
      )(result);
      return {
        items: decoded.workspaces.map(interpretDraftWorkspace),
      };
    },
  },
  {
    method: "workflow.draft_workspaces.get",
    label: "Inspect draft workspace",
    explanation: "Inspect one persisted workflow draft workspace",
    idempotency: "read",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(
        WorkflowDraftWorkspacesGetPayloadSchema,
      )(params, { onExcessProperty: "error" });
      const parts = ["uv run wf draft inspect", shellArg(p.workspace_id)];
      if (p.include_draft === true) parts.push("--include-draft");
      return parts.join(" ");
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(
        WorkflowDraftWorkspacesGetResultSchema,
      )(result);
      return interpretDraftWorkspace(decoded);
    },
  },
  {
    method: "workflow.artifacts.list",
    label: "List artifacts",
    explanation: "List workflow artifacts with pagination",
    idempotency: "read",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(WorkflowArtifactsListPayloadSchema)(
        params,
        { onExcessProperty: "error" },
      );
      const parts = ["uv run wf artifact list"];
      if (p.query != null) parts.push(`--query ${shellArg(p.query)}`);
      if (p.kind != null) parts.push(`--kind ${shellArg(p.kind)}`);
      if (p.cursor != null) parts.push(`--cursor ${shellArg(p.cursor)}`);
      if (p.limit != null) parts.push(`--limit ${p.limit}`);
      return parts.join(" ");
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(
        WorkflowArtifactsListResultSchema,
      )(result);
      return {
        items: decoded.nodes.map((node) => ({
          key: `${node.artifact_id}@${node.version}`,
          artifactId: node.artifact_id,
          version: node.version,
          kind: node.kind,
          displayName: node.display_name,
          description: node.description,
          outcomes: node.outcomes,
          requiredSources: node.required_sources,
          diagnosticCount: node.diagnostics.length,
        })),
        nextCursor: decoded.next_cursor,
        total: decoded.total,
      };
    },
  },
  {
    method: "workflow.artifacts.inspect",
    label: "Inspect artifact",
    explanation: "Inspect a workflow artifact by id and version",
    idempotency: "read",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(WorkflowArtifactsInspectPayloadSchema)(
        params,
        { onExcessProperty: "error" },
      );
      return `uv run wf artifact inspect ${shellArg(p.artifact_id)} --version ${p.version}`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(
        WorkflowArtifactsInspectResultSchema,
      )(result);
      return {
        artifactId: decoded.id,
        version: decoded.version,
        title: decoded.title,
        kind: decoded.kind,
        description: decoded.description,
        outcomes: decoded.outcomes,
        plan: decoded.plan,
        requiredCapabilities: decoded.required_capabilities,
        workflowDependencies: decoded.workflow_dependencies,
        createdFromCatalogVersion: decoded.created_from_catalog_version,
      };
    },
  },
  {
    method: "workflow.deployments.list",
    label: "List deployments",
    explanation: "List workflow deployments",
    idempotency: "read",
    equivalentCli: () => "uv run wf deploy list",
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(
        WorkflowDeploymentsListResultSchema,
      )(result);
      return {
        items: decoded.deployments.map((d) => ({
          id: d.id,
          artifactId: d.artifact_id,
          artifactVersion: d.artifact_version,
          bindingCount: d.binding_count,
          driftPolicy: d.drift_policy,
        })),
      };
    },
  },
  {
    method: "workflow.deployments.inspect",
    label: "Inspect deployment",
    explanation: "Inspect a workflow deployment by id",
    idempotency: "read",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(
        WorkflowDeploymentsInspectPayloadSchema,
      )(params, { onExcessProperty: "error" });
      return `uv run wf deploy inspect ${shellArg(p.deployment_id)}`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(
        WorkflowDeploymentsInspectResultSchema,
      )(result);
      return {
        id: decoded.id,
        artifactId: decoded.artifact_id,
        artifactVersion: decoded.artifact_version,
        bindings: decoded.bindings.map((b) => ({
          logicalSource: b.logical_source,
          concreteSource: b.concrete_source,
        })),
        driftPolicy: decoded.drift_policy,
      };
    },
  },
  {
    method: "workflow.deployments.validate",
    label: "Validate deployment",
    explanation: "Validate a workflow deployment",
    idempotency: "read",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(
        WorkflowDeploymentsValidatePayloadSchema,
      )(params, { onExcessProperty: "error" });
      return `uv run wf deploy validate ${shellArg(p.deployment_id)}`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(
        WorkflowDeploymentsValidateResultSchema,
      )(result);
      return {
        deploymentId: decoded.deployment_id,
        artifactId: decoded.artifact_id,
        artifactVersion: decoded.artifact_version,
        status: decoded.status,
        diagnostics: decoded.diagnostics,
        nextActions: interpretNextActions(decoded.next_actions),
      };
    },
  },
  {
    method: "workflow.runs.list",
    label: "List runs",
    explanation: "List workflow runs with pagination",
    idempotency: "read",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(WorkflowRunsListPayloadSchema)(
        params,
        { onExcessProperty: "error" },
      );
      const parts = ["uv run wf run list"];
      if (p.status != null) parts.push(`--status ${shellArg(p.status)}`);
      if (p.cursor != null) parts.push(`--cursor ${shellArg(p.cursor)}`);
      if (p.limit != null) parts.push(`--limit ${p.limit}`);
      return parts.join(" ");
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(WorkflowRunsListResultSchema)(
        result,
      );
      return {
        items: decoded.runs.map((run) => ({
          runId: run.run_id,
          deploymentId: run.deployment_id,
          artifactId: run.artifact_id,
          artifactVersion: run.artifact_version,
          status: run.status,
          resumeReadiness: run.resume_readiness,
          diagnosticCount: run.diagnostic_count,
          createdAt: run.created_at,
          updatedAt: run.updated_at,
        })),
        nextCursor: decoded.next_cursor,
        total: decoded.total,
      };
    },
  },
  {
    method: "workflow.runs.inspect",
    label: "Inspect run",
    explanation: "Inspect a workflow run by id",
    idempotency: "read",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(WorkflowRunsInspectPayloadSchema)(
        params,
        { onExcessProperty: "error" },
      );
      return `uv run wf run inspect ${shellArg(p.run_id)}`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(WorkflowRunsInspectResultSchema)(
        result,
      );
      return interpretRunDetail(decoded);
    },
  },
  {
    method: "workflow.runs.start",
    label: "Start run",
    explanation: "Start a workflow deployment run",
    idempotency: "write",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(WorkflowRunsStartPayloadSchema)(
        params,
        { onExcessProperty: "error" },
      );
      return `uv run wf run start ${shellArg(p.deployment_id)} --input '<json>'`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(WorkflowRunsStartResultSchema)(
        result,
        { onExcessProperty: "ignore" },
      );
      return interpretRunDetail(decoded);
    },
  },
  {
    method: "workflow.runs.resume",
    label: "Resume run",
    explanation: "Resume an interrupted workflow run",
    idempotency: "write",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(WorkflowRunsResumePayloadSchema)(
        params,
        { onExcessProperty: "error" },
      );
      return `uv run wf run resume ${shellArg(p.run_id)} --payload '<json>'`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(WorkflowRunsResumeResultSchema)(
        result,
        { onExcessProperty: "ignore" },
      );
      return interpretRunDetail(decoded);
    },
  },
  {
    method: "workflow.runs.trace",
    label: "Read run trace",
    explanation: "Read trace frames for a workflow run",
    idempotency: "read",
    equivalentCli: (params) => {
      const p = Schema.decodeUnknownSync(WorkflowRunsTracePayloadSchema)(
        params,
        { onExcessProperty: "error" },
      );
      const parts = ["uv run wf run trace", shellArg(p.run_id)];
      if (p.trace_range.start != null) {
        parts.push(`--from ${p.trace_range.start}`);
      }
      if (p.trace_range.limit != null) {
        parts.push(`--limit ${p.trace_range.limit}`);
      }
      return parts.join(" ");
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(WorkflowRunsTraceResultSchema)(result);
      const trace = decoded.trace.map((entry) => ({
        frameId: entry.frame_id,
        nodeId: entry.node_id,
        stepType: entry.step_type,
        outcome: entry.outcome,
        nextNodeId: entry.next_node_id,
        resolvedInput: entry.resolved_input,
        output: entry.output,
        stateChanges: entry.state_changes,
      }));
      return {
        runId: decoded.run_id,
        status: decoded.status,
        frames: trace,
        traceStart: decoded.trace_start,
        traceLimit: decoded.trace_limit,
        traceTruncated: decoded.trace_truncated,
      };
    },
  },
]);

export type OperationName = (typeof operationEntries)[number]["method"];

export const workflowRpcOperationNames: ReadonlyArray<OperationName> =
  Object.freeze(operationEntries.map(({ method }) => method));

const operationNameSet: ReadonlySet<string> = new Set(workflowRpcOperationNames);

export const isOperationName = (value: string): value is OperationName =>
  operationNameSet.has(value);

const registry: ReadonlyMap<string, OperationMeta> = new Map(
  operationEntries.map((entry) => [entry.method, entry]),
);

export const getOperationMeta = (method: string): OperationMeta | undefined =>
  registry.get(method);

export const listOperations = (): ReadonlyArray<OperationMeta> =>
  operationEntries;

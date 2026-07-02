import { Schema } from "effect";
import {
  WorkflowHealthResultSchema,
  WorkflowSourcesListPayloadSchema,
  WorkflowSourcesListResultSchema,
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
  WorkflowRunsResumePayloadSchema,
  WorkflowRunsTracePayloadSchema,
  WorkflowRunsTraceResultSchema,
} from "./rpcs.js";

export type OperationMeta = {
  readonly method: string;
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

/** Adapts a snake_case run detail from the server into camelCase for the browser. */
const interpretRunDetail = (decoded: {
  readonly run_id: string;
  readonly deployment_id: string;
  readonly artifact_id: string;
  readonly artifact_version: number;
  readonly status: string;
  readonly resume_readiness: string;
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

const operationEntries: ReadonlyArray<OperationMeta> = [
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
      if (p.cursor != null) parts.push(`--cursor ${p.cursor}`);
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
      return `uv run wf artifact inspect ${p.artifact_id} --version ${p.version}`;
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
      return `uv run wf deploy inspect ${p.deployment_id}`;
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
      return `uv run wf deploy validate ${p.deployment_id}`;
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
      return `uv run wf run inspect ${p.run_id}`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(WorkflowRunsInspectResultSchema)(
        result,
      );
      return {
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
      };
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
      return `uv run wf run start ${p.deployment_id} --input '<json>'`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(WorkflowRunsInspectResultSchema)(
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
      return `uv run wf run resume ${p.run_id} --payload '<json>'`;
    },
    interpret: (result) => {
      const decoded = Schema.decodeUnknownSync(WorkflowRunsInspectResultSchema)(
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
      return `uv run wf run trace ${p.run_id} --from ${p.trace_range.start} --limit ${p.trace_range.limit}`;
    },
    interpret: (result) => {
      const r = result as Record<string, unknown>;
      const trace = (r.trace as ReadonlyArray<Record<string, unknown>> ?? []).map((entry) => ({
        nodeId: entry.node_id,
        stepType: entry.step_type,
        outcome: entry.outcome,
        resolvedInput: entry.resolved_input,
        output: entry.output,
        stateChanges: entry.state_changes,
      }));
      return {
        runId: r.run_id,
        status: r.status,
        frames: trace,
        traceStart: r.trace_start,
        traceLimit: r.trace_limit,
        traceTruncated: r.trace_truncated,
      };
    },
  },
];

const registry: ReadonlyMap<string, OperationMeta> = new Map(
  operationEntries.map((entry) => [entry.method, entry]),
);

export const getOperationMeta = (method: string): OperationMeta | undefined =>
  registry.get(method);

export const listOperations = (): ReadonlyArray<OperationMeta> =>
  operationEntries;

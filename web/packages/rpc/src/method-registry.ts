import { Schema } from "effect";
import {
  WorkflowHealthResultSchema,
  WorkflowSourcesListPayloadSchema,
  WorkflowSourcesListResultSchema,
} from "./rpcs.js";

export type OperationMeta = {
  readonly method: string;
  readonly label: string;
  readonly explanation: string;
  readonly idempotency: "read";
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
];

const registry: ReadonlyMap<string, OperationMeta> = new Map(
  operationEntries.map((entry) => [entry.method, entry]),
);

export const getOperationMeta = (method: string): OperationMeta | undefined =>
  registry.get(method);

export const listOperations = (): ReadonlyArray<OperationMeta> =>
  operationEntries;

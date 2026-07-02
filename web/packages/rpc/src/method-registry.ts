export type OperationMeta = {
  readonly method: string;
  readonly label: string;
  readonly explanation: string;
  readonly idempotency: "read";
  readonly equivalentCli: (params: unknown) => string;
  readonly interpret: (result: unknown) => unknown;
};

const registry: ReadonlyMap<string, OperationMeta> = new Map([
  [
    "workflow.health",
    {
      method: "workflow.health",
      label: "Health check",
      explanation: "Check if the workflow server is running",
      idempotency: "read",
      equivalentCli: () => "uv run wf status",
      interpret: (result) => result,
    },
  ],
  [
    "workflow.sources.list",
    {
      method: "workflow.sources.list",
      label: "List sources",
      explanation: "List registered data sources with pagination",
      idempotency: "read",
      equivalentCli: (params) => {
        const p = params as { cursor?: string; limit?: number };
        const parts = ["uv run wf source list"];
        if (p.limit != null) parts.push(`--limit ${p.limit}`);
        if (p.cursor != null) parts.push(`--cursor ${p.cursor}`);
        return parts.join(" ");
      },
      interpret: (result) => result,
    },
  ],
]);

export const getOperationMeta = (method: string): OperationMeta | undefined =>
  registry.get(method);

export const listOperations = (): ReadonlyArray<OperationMeta> =>
  Array.from(registry.values());

import * as v from "valibot";

export type JsonObject = Record<string, unknown>;

export type CreateEmptyDraftInput = {
  readonly workspaceId: string;
  readonly name: string;
  readonly title?: string | null;
  readonly inputSchema?: JsonObject | null;
  readonly stateSchema?: JsonObject | null;
  readonly outputSchema?: JsonObject | null;
  readonly outcomes?: ReadonlyArray<string>;
};

export type CreateFromCapabilityInput = {
  readonly workspaceId: string;
  readonly capabilityName: string;
  readonly name?: string | null;
  readonly title?: string | null;
  readonly inputSchema?: JsonObject | null;
  readonly stateSchema?: JsonObject | null;
  readonly outputSchema?: JsonObject | null;
  readonly input?: ReadonlyArray<unknown> | null;
  readonly output?: ReadonlyArray<unknown> | null;
  readonly inputMap?: Record<string, string> | null;
  readonly outputMap?: Record<string, string> | null;
  readonly errorMessageSource?: unknown;
};

export type AddCapabilityStepInput = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly stepId: string;
  readonly capabilityName: string;
  readonly routeFromStep?: string | null;
  readonly routeFromOutcome?: string;
  readonly routes?: Record<string, string> | null;
  readonly inputMap?: Record<string, string> | null;
  readonly inputBindings?: ReadonlyArray<unknown> | null;
  readonly bindOutputs?: Record<string, string>;
  readonly description?: string | null;
  readonly retry?: number | null;
  readonly timeoutSeconds?: number | null;
};

export type UpdateCapabilityStepInput = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly stepId: string;
  readonly update: {
    readonly description?: string | null;
    readonly input?: ReadonlyArray<unknown> | null;
    readonly retry?: number | null;
    readonly timeoutSeconds?: number | null;
  };
};

export type SetDraftRouteInput = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly stepId: string;
  readonly outcome: string;
  readonly target: string;
};

const decode = <T>(
  label: string,
  schema: v.GenericSchema<unknown, T>,
  value: unknown,
): T => {
  const result = v.safeParse(schema, value);
  if (result.success) return result.output;
  throw new Error(
    `${label} is malformed: ${result.issues[0]?.message ?? "unknown issue"}`,
  );
};

const DraftDiagnosticSchema = v.object({
  code: v.string(),
  path: v.string(),
  message: v.string(),
  stepId: v.nullish(v.string(), null),
  repairHint: v.nullish(v.string(), null),
  details: v.record(v.string(), v.unknown()),
});

const DraftWorkspaceSummarySchema = v.object({
  name: v.unknown(),
  start: v.unknown(),
  stepCount: v.number(),
  routeCount: v.number(),
  steps: v.array(v.string()),
});

const DraftWorkspaceSchema = v.object({
  workspaceId: v.string(),
  revision: v.number(),
  title: v.nullish(v.string(), null),
  status: v.union([
    v.literal("valid"),
    v.literal("invalid"),
    v.literal("conflict"),
  ]),
  diagnostics: v.array(DraftDiagnosticSchema),
  summary: DraftWorkspaceSummarySchema,
  draft: v.optional(v.nullish(v.record(v.string(), v.unknown()), null), null),
});

const DraftWorkspacePageSchema = v.object({
  items: v.array(DraftWorkspaceSchema),
});

export type DraftDiagnostic = v.InferOutput<typeof DraftDiagnosticSchema>;
export type DraftWorkspaceSummary = v.InferOutput<
  typeof DraftWorkspaceSummarySchema
>;
export type DraftWorkspace = v.InferOutput<typeof DraftWorkspaceSchema>;
export type DraftWorkspacePage = v.InferOutput<typeof DraftWorkspacePageSchema>;

export const decodeDraftWorkspacePage = (
  value: unknown,
): DraftWorkspacePage => decode("DraftWorkspacePage", DraftWorkspacePageSchema, value);

export const decodeDraftWorkspace = (value: unknown): DraftWorkspace =>
  decode("DraftWorkspace", DraftWorkspaceSchema, value);

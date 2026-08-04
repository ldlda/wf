import * as v from "valibot";

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

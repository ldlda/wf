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

// Artifact schemas
const ArtifactSummarySchema = v.object({
  key: v.string(),
  artifactId: v.string(),
  version: v.number(),
  kind: v.string(),
  displayName: v.string(),
  description: v.nullish(v.string(), null),
  outcomes: v.array(v.string()),
  requiredSources: v.array(v.string()),
  diagnosticCount: v.number(),
});

const ArtifactListSchema = v.object({
  items: v.array(ArtifactSummarySchema),
  nextCursor: v.nullish(v.string(), null),
  total: v.number(),
});

const ArtifactDetailSchema = v.object({
  artifactId: v.string(),
  version: v.number(),
  title: v.string(),
  kind: v.string(),
  description: v.nullish(v.string(), null),
  outcomes: v.array(v.string()),
  plan: v.record(v.string(), v.unknown()),
  requiredCapabilities: v.unknown(),
  workflowDependencies: v.record(v.string(), v.number()),
  createdFromCatalogVersion: v.nullish(v.string(), null),
});

// Deployment schemas
const DeploymentBindingSchema = v.object({
  logicalSource: v.string(),
  concreteSource: v.string(),
});

const DeploymentSummarySchema = v.object({
  id: v.string(),
  artifactId: v.string(),
  artifactVersion: v.number(),
  bindingCount: v.number(),
  driftPolicy: v.string(),
});

const DeploymentListSchema = v.object({
  items: v.array(DeploymentSummarySchema),
});

const DeploymentDetailSchema = v.object({
  id: v.string(),
  artifactId: v.string(),
  artifactVersion: v.number(),
  bindings: v.array(DeploymentBindingSchema),
  driftPolicy: v.string(),
});

const DeploymentValidationSchema = v.object({
  deploymentId: v.string(),
  artifactId: v.string(),
  artifactVersion: v.number(),
  status: v.union([v.literal("runnable"), v.literal("unrunnable")]),
  diagnostics: v.array(v.unknown()),
  nextActions: v.object({
    canContinue: v.boolean(),
    canSaveNow: v.nullish(v.boolean(), null),
    recommendedNextTool: v.nullish(v.string(), null),
    reason: v.string(),
    patchExamples: v.array(v.unknown()),
    warnings: v.array(v.string()),
  }),
});

// Run schemas
const RunSummarySchema = v.object({
  runId: v.string(),
  deploymentId: v.string(),
  artifactId: v.string(),
  artifactVersion: v.number(),
  status: v.string(),
  resumeReadiness: v.string(),
  diagnosticCount: v.number(),
});

const RunInterruptSchema = v.object({
  kind: v.string(),
  payload: v.record(v.string(), v.unknown()),
  outcomes: v.array(v.string()),
});

const RunListSchema = v.object({
  items: v.array(RunSummarySchema),
  nextCursor: v.nullish(v.string(), null),
  total: v.number(),
});

const RunDetailSchema = v.object({
  runId: v.string(),
  deploymentId: v.string(),
  artifactId: v.string(),
  artifactVersion: v.number(),
  status: v.string(),
  resumeReadiness: v.string(),
  interrupt: v.nullish(RunInterruptSchema, null),
  outcome: v.nullish(v.string(), null),
  error: v.nullish(v.string(), null),
  output: v.nullish(v.record(v.string(), v.unknown()), null),
  diagnostics: v.array(v.unknown()),
  traceCount: v.number(),
  nextActions: v.object({
    canContinue: v.boolean(),
    canSaveNow: v.nullish(v.boolean(), null),
    recommendedNextTool: v.nullish(v.string(), null),
    reason: v.string(),
    patchExamples: v.array(v.unknown()),
    warnings: v.array(v.string()),
  }),
});

// Trace schemas
const TraceFrameSchema = v.object({
  nodeId: v.string(),
  stepType: v.string(),
  outcome: v.string(),
  resolvedInput: v.record(v.string(), v.unknown()),
  output: v.record(v.string(), v.unknown()),
  stateChanges: v.record(v.string(), v.unknown()),
});

const TracePageSchema = v.object({
  frames: v.array(TraceFrameSchema),
  traceStart: v.number(),
  traceLimit: v.number(),
  traceTruncated: v.boolean(),
});

// Exported types
export type ArtifactSummary = v.InferOutput<typeof ArtifactSummarySchema>;
export type ArtifactDetail = v.InferOutput<typeof ArtifactDetailSchema>;
export type DeploymentSummary = v.InferOutput<typeof DeploymentSummarySchema>;
export type DeploymentDetail = v.InferOutput<typeof DeploymentDetailSchema>;
export type DeploymentValidation = v.InferOutput<typeof DeploymentValidationSchema>;
export type RunSummary = v.InferOutput<typeof RunSummarySchema>;
export type RunDetail = v.InferOutput<typeof RunDetailSchema>;
export type TraceFrame = v.InferOutput<typeof TraceFrameSchema>;
export type TracePage = v.InferOutput<typeof TracePageSchema>;

// Exported decoders
export const decodeArtifactList = (value: unknown): ArtifactList =>
  decode("ArtifactList", ArtifactListSchema, value);

export const decodeArtifactDetail = (value: unknown): ArtifactDetail =>
  decode("ArtifactDetail", ArtifactDetailSchema, value);

export const decodeDeploymentList = (value: unknown): DeploymentList =>
  decode("DeploymentList", DeploymentListSchema, value);

export const decodeDeploymentDetail = (value: unknown): DeploymentDetail =>
  decode("DeploymentDetail", DeploymentDetailSchema, value);

export const decodeDeploymentValidation = (
  value: unknown,
): DeploymentValidation =>
  decode("DeploymentValidation", DeploymentValidationSchema, value);

export const decodeRunList = (value: unknown): RunList =>
  decode("RunList", RunListSchema, value);

export const decodeRunDetail = (value: unknown): RunDetail =>
  decode("RunDetail", RunDetailSchema, value);

export const decodeTracePage = (value: unknown): TracePage =>
  decode("TracePage", TracePageSchema, value);

// List wrapper types
export type ArtifactList = v.InferOutput<typeof ArtifactListSchema>;
export type DeploymentList = v.InferOutput<typeof DeploymentListSchema>;
export type RunList = v.InferOutput<typeof RunListSchema>;

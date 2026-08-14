import * as v from "valibot";

export type AuthoringPathOrigin =
  | "workflow_input"
  | "workflow_state"
  | "runtime_context"
  | "step_input"
  | "step_output"
  | "workflow_output";

export type AuthoringPathAvailability = "available" | "conditional";

export type AuthoringPathUse =
  | "step_input"
  | "step_output_source"
  | "state_target"
  | "workflow_output";

export type AuthoringPathOption = {
  readonly path: string;
  readonly label: string;
  readonly origin: AuthoringPathOrigin;
  readonly schema: Readonly<Record<string, unknown>>;
  readonly required: boolean;
  readonly availability: AuthoringPathAvailability;
  readonly uses: ReadonlyArray<AuthoringPathUse>;
  readonly description?: string | undefined;
  readonly reason?: string | undefined;
};

export type AuthoringStepContract = {
  readonly stepId: string;
  readonly label: string;
  readonly description?: string | undefined;
  readonly inputTargets?: ReadonlyArray<AuthoringPathOption> | undefined;
  readonly outputSources?: ReadonlyArray<AuthoringPathOption> | undefined;
  readonly outcomes?: ReadonlyArray<string> | undefined;
};

export type AuthoringContractInventory = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly selectedStepId: string | null;
  readonly readableSources: ReadonlyArray<AuthoringPathOption>;
  readonly stepInputTargets: ReadonlyArray<AuthoringPathOption>;
  readonly stepOutputSources: ReadonlyArray<AuthoringPathOption>;
  readonly stateTargets: ReadonlyArray<AuthoringPathOption>;
  readonly workflowOutputTargets: ReadonlyArray<AuthoringPathOption>;
  readonly entrySteps: ReadonlyArray<AuthoringStepContract>;
  readonly workflowOutcomes: ReadonlyArray<string>;
  readonly warnings: ReadonlyArray<string>;
};

const JsonObjectSchema = v.record(v.string(), v.unknown());
const PositiveRevisionSchema = v.pipe(v.number(), v.integer(), v.minValue(1));
const SelectedStepIdSchema = v.nullable(v.pipe(v.string(), v.minLength(1)));

const AuthoringPathOriginSchema = v.union([
  v.literal("workflow_input"),
  v.literal("workflow_state"),
  v.literal("runtime_context"),
  v.literal("step_input"),
  v.literal("step_output"),
  v.literal("workflow_output"),
]);

const AuthoringPathAvailabilitySchema = v.union([
  v.literal("available"),
  v.literal("conditional"),
]);

const AuthoringPathUseSchema = v.union([
  v.literal("step_input"),
  v.literal("step_output_source"),
  v.literal("state_target"),
  v.literal("workflow_output"),
]);

const AuthoringPathOptionSchema = v.pipe(
  v.object({
    path: v.string(),
    label: v.string(),
    origin: AuthoringPathOriginSchema,
    schema: JsonObjectSchema,
    required: v.boolean(),
    availability: AuthoringPathAvailabilitySchema,
    uses: v.array(AuthoringPathUseSchema),
    description: v.optional(v.string()),
    reason: v.optional(v.string()),
  }),
  v.check(
    (option) =>
      option.availability !== "conditional" ||
      (option.reason !== undefined && option.reason.trim().length > 0),
    "conditional authoring options require a non-empty reason",
  ),
);

const AuthoringStepContractWireSchema = v.object({
  step_id: v.string(),
  label: v.string(),
  description: v.optional(v.string()),
  input_targets: v.optional(v.array(AuthoringPathOptionSchema)),
  output_sources: v.optional(v.array(AuthoringPathOptionSchema)),
  outcomes: v.optional(v.array(v.string())),
});

const AuthoringContractInventoryWireSchema = v.object({
  workspace_id: v.string(),
  revision: PositiveRevisionSchema,
  selected_step_id: SelectedStepIdSchema,
  readable_sources: v.array(AuthoringPathOptionSchema),
  step_input_targets: v.array(AuthoringPathOptionSchema),
  step_output_sources: v.array(AuthoringPathOptionSchema),
  state_targets: v.array(AuthoringPathOptionSchema),
  workflow_output_targets: v.array(AuthoringPathOptionSchema),
  entry_steps: v.array(AuthoringStepContractWireSchema),
  workflow_outcomes: v.array(v.string()),
  warnings: v.array(v.string()),
});

const AuthoringStepContractBrowserSchema = v.object({
  stepId: v.string(),
  label: v.string(),
  description: v.optional(v.string()),
  inputTargets: v.optional(v.array(AuthoringPathOptionSchema)),
  outputSources: v.optional(v.array(AuthoringPathOptionSchema)),
  outcomes: v.optional(v.array(v.string())),
});

const AuthoringContractInventoryBrowserSchema = v.object({
  workspaceId: v.string(),
  revision: PositiveRevisionSchema,
  selectedStepId: SelectedStepIdSchema,
  readableSources: v.array(AuthoringPathOptionSchema),
  stepInputTargets: v.array(AuthoringPathOptionSchema),
  stepOutputSources: v.array(AuthoringPathOptionSchema),
  stateTargets: v.array(AuthoringPathOptionSchema),
  workflowOutputTargets: v.array(AuthoringPathOptionSchema),
  entrySteps: v.array(AuthoringStepContractBrowserSchema),
  workflowOutcomes: v.array(v.string()),
  warnings: v.array(v.string()),
});

type AuthoringPathOptionWire = v.InferOutput<typeof AuthoringPathOptionSchema>;
type AuthoringStepContractWire = v.InferOutput<typeof AuthoringStepContractWireSchema>;
type AuthoringContractInventoryWire = v.InferOutput<
  typeof AuthoringContractInventoryWireSchema
>;
type AuthoringContractInventoryBrowser = v.InferOutput<
  typeof AuthoringContractInventoryBrowserSchema
>;

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

const mapPathOption = (option: AuthoringPathOptionWire): AuthoringPathOption => ({
  path: option.path,
  label: option.label,
  origin: option.origin,
  schema: option.schema,
  required: option.required,
  availability: option.availability,
  uses: option.uses,
  ...(option.description === undefined ? {} : { description: option.description }),
  ...(option.reason === undefined ? {} : { reason: option.reason }),
});

const mapStepContract = (step: AuthoringStepContractWire): AuthoringStepContract => ({
  stepId: step.step_id,
  label: step.label,
  ...(step.description === undefined ? {} : { description: step.description }),
  ...(step.input_targets === undefined
    ? {}
    : { inputTargets: step.input_targets.map(mapPathOption) }),
  ...(step.output_sources === undefined
    ? {}
    : { outputSources: step.output_sources.map(mapPathOption) }),
  ...(step.outcomes === undefined ? {} : { outcomes: step.outcomes }),
});

const mapInventory = (
  inventory: AuthoringContractInventoryWire,
): AuthoringContractInventory => ({
  workspaceId: inventory.workspace_id,
  revision: inventory.revision,
  selectedStepId: inventory.selected_step_id,
  readableSources: inventory.readable_sources.map(mapPathOption),
  stepInputTargets: inventory.step_input_targets.map(mapPathOption),
  stepOutputSources: inventory.step_output_sources.map(mapPathOption),
  stateTargets: inventory.state_targets.map(mapPathOption),
  workflowOutputTargets: inventory.workflow_output_targets.map(mapPathOption),
  entrySteps: inventory.entry_steps.map(mapStepContract),
  workflowOutcomes: inventory.workflow_outcomes,
  warnings: inventory.warnings,
});

const mapBrowserInventory = (
  inventory: AuthoringContractInventoryBrowser,
): AuthoringContractInventory => ({
  workspaceId: inventory.workspaceId,
  revision: inventory.revision,
  selectedStepId: inventory.selectedStepId,
  readableSources: inventory.readableSources,
  stepInputTargets: inventory.stepInputTargets,
  stepOutputSources: inventory.stepOutputSources,
  stateTargets: inventory.stateTargets,
  workflowOutputTargets: inventory.workflowOutputTargets,
  entrySteps: inventory.entrySteps,
  workflowOutcomes: inventory.workflowOutcomes,
  warnings: inventory.warnings,
});

const AuthoringContractResponseSchema = v.union([
  AuthoringContractInventoryWireSchema,
  AuthoringContractInventoryBrowserSchema,
]);

export const decodeAuthoringContractInventory = (
  value: unknown,
): AuthoringContractInventory => {
  const decoded = decode(
    "AuthoringContractInventory",
    AuthoringContractResponseSchema,
    value,
  );
  return "workspace_id" in decoded ? mapInventory(decoded) : mapBrowserInventory(decoded);
};

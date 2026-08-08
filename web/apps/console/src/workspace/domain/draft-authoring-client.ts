import type { OperationName } from "../../connection/contracts.js";
import {
  decodeDraftWorkspace,
  type AddCapabilityStepInput,
  type CreateEmptyDraftInput,
  type CreateFromCapabilityInput,
  type DraftWorkspace,
  type SetDraftRouteInput,
  type UpdateCapabilityStepInput,
} from "./draft-workspace-models.js";
import { ConsoleClientError } from "./errors.js";
import type { ConsoleWriteExecutor } from "./write-executor.js";

export interface DraftAuthoringClient {
  createEmpty(input: CreateEmptyDraftInput): Promise<DraftWorkspace>;
  createFromCapability(input: CreateFromCapabilityInput): Promise<DraftWorkspace>;
  addCapabilityStep(input: AddCapabilityStepInput): Promise<DraftWorkspace>;
  updateCapabilityStep(input: UpdateCapabilityStepInput): Promise<DraftWorkspace>;
  setRoute(input: SetDraftRouteInput): Promise<DraftWorkspace>;
  validate(workspaceId: string): Promise<DraftWorkspace>;
}

const invalidInput = (operation: OperationName, message: string): ConsoleClientError =>
  new ConsoleClientError("operation", operation, message);

const requireIdentifier = (
  operation: OperationName,
  value: string,
  label: string,
): string => {
  const normalizedValue = value.trim();
  if (!normalizedValue) throw invalidInput(operation, `${label} must not be blank`);
  return normalizedValue;
};

const optionalIdentifier = (
  operation: OperationName,
  value: string | null | undefined,
  label: string,
): string | null | undefined =>
  value === undefined || value === null
    ? value
    : requireIdentifier(operation, value, label);

const ifDefined = <T>(
  target: Record<string, unknown>,
  key: string,
  value: T | undefined,
): void => {
  if (value !== undefined) target[key] = value;
};

export const createDraftAuthoringClient = (
  executor: ConsoleWriteExecutor,
): DraftAuthoringClient => ({
  createEmpty: async (input) => {
    const operation = "workflow.draft_workspaces.create_empty";
    const params: Record<string, unknown> = {
      workspace_id: requireIdentifier(operation, input.workspaceId, "workspace id"),
      name: requireIdentifier(operation, input.name, "draft name"),
    };
    ifDefined(params, "title", input.title);
    ifDefined(params, "input_schema", input.inputSchema);
    ifDefined(params, "state_schema", input.stateSchema);
    ifDefined(params, "output_schema", input.outputSchema);
    ifDefined(params, "outcomes", input.outcomes);
    return executor.run(operation, params, decodeDraftWorkspace);
  },

  createFromCapability: async (input) => {
    const operation = "workflow.draft_workspaces.create_from_capability";
    const params: Record<string, unknown> = {
      workspace_id: requireIdentifier(operation, input.workspaceId, "workspace id"),
      capability_name: requireIdentifier(
        operation,
        input.capabilityName,
        "capability name",
      ),
    };
    ifDefined(params, "name", optionalIdentifier(operation, input.name, "draft name"));
    ifDefined(params, "title", input.title);
    ifDefined(params, "input_schema", input.inputSchema);
    ifDefined(params, "state_schema", input.stateSchema);
    ifDefined(params, "output_schema", input.outputSchema);
    ifDefined(params, "input", input.input);
    ifDefined(params, "output", input.output);
    ifDefined(params, "input_map", input.inputMap);
    ifDefined(params, "output_map", input.outputMap);
    ifDefined(params, "error_message_source", input.errorMessageSource);
    return executor.run(operation, params, decodeDraftWorkspace);
  },

  addCapabilityStep: async (input) => {
    const operation = "workflow.draft_workspaces.add_step_from_capability";
    const params: Record<string, unknown> = {
      workspace_id: requireIdentifier(operation, input.workspaceId, "workspace id"),
      revision: input.revision,
      step_id: requireIdentifier(operation, input.stepId, "step id"),
      capability_name: requireIdentifier(
        operation,
        input.capabilityName,
        "capability name",
      ),
    };
    ifDefined(
      params,
      "route_from_step",
      optionalIdentifier(operation, input.routeFromStep, "route source step"),
    );
    ifDefined(
      params,
      "route_from_outcome",
      optionalIdentifier(operation, input.routeFromOutcome, "route source outcome"),
    );
    ifDefined(params, "routes", input.routes);
    ifDefined(params, "input_map", input.inputMap);
    ifDefined(params, "input_bindings", input.inputBindings);
    ifDefined(params, "bind_outputs", input.bindOutputs);
    ifDefined(params, "desc", input.description);
    ifDefined(params, "retry", input.retry);
    ifDefined(params, "timeout_seconds", input.timeoutSeconds);
    return executor.run(operation, params, decodeDraftWorkspace);
  },

  updateCapabilityStep: async (input) => {
    const operation = "workflow.draft_workspaces.update_capability_step";
    const update: Record<string, unknown> = {};
    ifDefined(update, "desc", input.update.description);
    ifDefined(update, "input", input.update.input);
    ifDefined(update, "retry", input.update.retry);
    ifDefined(update, "timeout_seconds", input.update.timeoutSeconds);
    return executor.run(
      operation,
      {
        workspace_id: requireIdentifier(operation, input.workspaceId, "workspace id"),
        revision: input.revision,
        step_id: requireIdentifier(operation, input.stepId, "step id"),
        update,
      },
      decodeDraftWorkspace,
    );
  },

  setRoute: async (input) => {
    const operation = "workflow.draft_workspaces.set_route";
    return executor.run(
      operation,
      {
        workspace_id: requireIdentifier(operation, input.workspaceId, "workspace id"),
        revision: input.revision,
        step_id: requireIdentifier(operation, input.stepId, "step id"),
        outcome: requireIdentifier(operation, input.outcome, "outcome"),
        target: requireIdentifier(operation, input.target, "route target"),
      },
      decodeDraftWorkspace,
    );
  },

  validate: async (workspaceId) => {
    const operation = "workflow.draft_workspaces.validate";
    return executor.run(
      operation,
      { workspace_id: requireIdentifier(operation, workspaceId, "workspace id") },
      decodeDraftWorkspace,
    );
  },
});

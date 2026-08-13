import { describe, expect, it, vi } from "vitest";
import type { OperationName } from "../../connection/contracts.js";
import {
  decodeDraftWorkspace,
  type AddCapabilityStepInput,
  type CreateEmptyDraftInput,
  type CreateFromCapabilityInput,
  type InputBinding,
  type StepInputBinding,
  type InputPathBinding,
  type InputValueBinding,
  type OutputBinding,
  type SetDraftRouteInput,
  type SetStepInputBindingsInput,
  type SetStepOutputBindingsInput,
  type UpdateCapabilityStepInput,
} from "./draft-workspace-models.js";
import { createDraftAuthoringClient } from "./draft-authoring-client.js";
import type { ConsoleWriteExecutor } from "./write-executor.js";

const canonicalWorkspace = {
  workspaceId: "draft-report",
  revision: 3,
  title: "Report",
  status: "valid" as const,
  diagnostics: [],
  summary: {
    name: "report",
    start: "read",
    stepCount: 1,
    routeCount: 0,
    steps: ["read"],
  },
  draft: { steps: [] },
};

const pathBinding = {
  target: "text",
  path: "input.text",
} satisfies InputPathBinding;

const valueBinding = {
  target: "mode",
  value: { value: "full" },
} satisfies InputValueBinding;

const canonicalBindings = [pathBinding, valueBinding] satisfies ReadonlyArray<InputBinding>;

const createExecutor = () => {
  const run = vi.fn();
  const executor: ConsoleWriteExecutor = {
    run: <T>(
      operation: OperationName,
      params: unknown,
      decode: (value: unknown) => T,
    ): Promise<T> => {
      run(operation, params, decode);
      return Promise.resolve(decode(canonicalWorkspace));
    },
  };
  return { executor, run };
};

describe("DraftAuthoringClient", () => {
  it("lowers all six authoring operations and decodes canonical workspaces", async () => {
    const { executor: writeExecutor, run } = createExecutor();
    const client = createDraftAuthoringClient(writeExecutor);

    const createEmptyInput = {
      workspaceId: "  draft-empty  ",
      name: "  empty  ",
      title: "Empty",
      inputSchema: { type: "object" },
      stateSchema: { type: "object" },
      outputSchema: { type: "object" },
      outcomes: ["done"],
    } satisfies CreateEmptyDraftInput;
    const createFromCapabilityInput = {
      workspaceId: "  draft-report  ",
      capabilityName: "  demo.read  ",
      name: "  report  ",
      title: "Report",
      inputSchema: { type: "object" },
      stateSchema: null,
      outputSchema: { type: "object" },
      input: [{ target: "text", value: "hello" }],
      output: null,
      inputMap: { text: "input.text" },
      outputMap: null,
      errorMessageSource: "error.message",
    } satisfies CreateFromCapabilityInput;
    const addCapabilityStepInput = {
      workspaceId: "  draft-report  ",
      revision: 3,
      stepId: "  enrich  ",
      capabilityName: "  demo.enrich  ",
      routeFromStep: "  read  ",
      routeFromOutcome: "  success  ",
      routes: { success: "enrich" },
      inputMap: { text: "input.text" },
      inputBindings: canonicalBindings,
      bindOutputs: { result: "state.result" },
      description: "Enrich report",
      retry: 2,
      timeoutSeconds: 30,
    } satisfies AddCapabilityStepInput;
    const updateCapabilityStepInput = {
      workspaceId: "  draft-report  ",
      revision: 3,
      stepId: "  enrich  ",
      update: {
        description: "Updated",
        input: [valueBinding],
        retry: null,
        timeoutSeconds: 45,
      },
    } satisfies UpdateCapabilityStepInput;
    const setRouteInput = {
      workspaceId: "  draft-report  ",
      revision: 3,
      stepId: "  read  ",
      outcome: "  success  ",
      target: "  enrich  ",
    } satisfies SetDraftRouteInput;

    await expect(client.createEmpty(createEmptyInput)).resolves.toEqual(canonicalWorkspace);
    await expect(client.createFromCapability(createFromCapabilityInput)).resolves.toEqual(
      canonicalWorkspace,
    );
    await expect(client.addCapabilityStep(addCapabilityStepInput)).resolves.toEqual(
      canonicalWorkspace,
    );
    await expect(client.updateCapabilityStep(updateCapabilityStepInput)).resolves.toEqual(
      canonicalWorkspace,
    );
    await expect(client.setRoute(setRouteInput)).resolves.toEqual(canonicalWorkspace);
    await expect(client.validate("  draft-report  ")).resolves.toEqual(canonicalWorkspace);

    expect(run).toHaveBeenNthCalledWith(
      1,
      "workflow.draft_workspaces.create_empty",
      {
        workspace_id: "draft-empty",
        name: "empty",
        title: "Empty",
        input_schema: { type: "object" },
        state_schema: { type: "object" },
        output_schema: { type: "object" },
        outcomes: ["done"],
      },
      decodeDraftWorkspace,
    );
    expect(run).toHaveBeenNthCalledWith(
      2,
      "workflow.draft_workspaces.create_from_capability",
      {
        workspace_id: "draft-report",
        capability_name: "demo.read",
        name: "report",
        title: "Report",
        input_schema: { type: "object" },
        state_schema: null,
        output_schema: { type: "object" },
        input: [{ target: "text", value: "hello" }],
        output: null,
        input_map: { text: "input.text" },
        output_map: null,
        error_message_source: "error.message",
      },
      decodeDraftWorkspace,
    );
    expect(run).toHaveBeenNthCalledWith(
      3,
      "workflow.draft_workspaces.add_step_from_capability",
      {
        workspace_id: "draft-report",
        revision: 3,
        step_id: "enrich",
        capability_name: "demo.enrich",
        route_from_step: "read",
        route_from_outcome: "success",
        routes: { success: "enrich" },
        input_map: { text: "input.text" },
        input_bindings: canonicalBindings,
        bind_outputs: { result: "state.result" },
        desc: "Enrich report",
        retry: 2,
        timeout_seconds: 30,
      },
      decodeDraftWorkspace,
    );
    expect(run).toHaveBeenNthCalledWith(
      4,
      "workflow.draft_workspaces.update_capability_step",
      {
        workspace_id: "draft-report",
        revision: 3,
        step_id: "enrich",
        update: {
          desc: "Updated",
          input: [valueBinding],
          retry: null,
          timeout_seconds: 45,
        },
      },
      decodeDraftWorkspace,
    );
    expect(run).toHaveBeenNthCalledWith(
      5,
      "workflow.draft_workspaces.set_route",
      {
        workspace_id: "draft-report",
        revision: 3,
        step_id: "read",
        outcome: "success",
        target: "enrich",
      },
      decodeDraftWorkspace,
    );
    expect(run).toHaveBeenNthCalledWith(
      6,
      "workflow.draft_workspaces.validate",
      { workspace_id: "draft-report" },
      decodeDraftWorkspace,
    );
  });

  it("rejects blank identifiers before invoking the executor", async () => {
    const { executor: writeExecutor, run } = createExecutor();
    const client = createDraftAuthoringClient(writeExecutor);

    await expect(client.validate(" \t")).rejects.toMatchObject({
      kind: "operation",
      operation: "workflow.draft_workspaces.validate",
    });
    await expect(
      client.addCapabilityStep({
        workspaceId: "draft-report",
        revision: 1,
        stepId: " ",
        capabilityName: "demo.read",
      }),
    ).rejects.toMatchObject({
      kind: "operation",
      operation: "workflow.draft_workspaces.add_step_from_capability",
    });
    expect(run).not.toHaveBeenCalled();
  });

  it("rejects malformed canonical workspaces through the decoder", async () => {
    const writeExecutor: ConsoleWriteExecutor = {
      run: <T>(
        _operation: OperationName,
        _params: unknown,
        decode: (value: unknown) => T,
      ): Promise<T> =>
        Promise.resolve(decode({ workspaceId: "draft-report" })),
    };
    const client = createDraftAuthoringClient(writeExecutor);

    await expect(client.validate("draft-report")).rejects.toThrow(
      /DraftWorkspace is malformed/,
    );
  });

  it("sets input bindings with canonical structural paths and preserves null values", async () => {
    const { executor: writeExecutor, run } = createExecutor();
    const client = createDraftAuthoringClient(writeExecutor);
    const bindings = [
      {
        path: { root: "context", parts: ["request", "text"] },
        target: { root: "local", parts: ["text"] },
      },
      {
        target: { root: "local", parts: ["optional"] },
        value: null,
      },
    ] satisfies SetStepInputBindingsInput["bindings"];
    const input = {
      workspaceId: " report ",
      revision: 7,
      stepId: " render ",
      bindings,
    } satisfies SetStepInputBindingsInput;

    await expect(client.setStepInputBindings(input)).resolves.toEqual(canonicalWorkspace);

    expect(run).toHaveBeenCalledWith(
      "workflow.draft_workspaces.set_step_input_bindings",
      {
        workspace_id: "report",
        revision: 7,
        step_id: "render",
        bindings,
      },
      decodeDraftWorkspace,
    );
    bindings.splice(0, bindings.length);
    expect(run).toHaveBeenCalledWith(
      "workflow.draft_workspaces.set_step_input_bindings",
      {
        workspace_id: "report",
        revision: 7,
        step_id: "render",
        bindings: [
          {
            path: { root: "context", parts: ["request", "text"] },
            target: { root: "local", parts: ["text"] },
          },
          {
            target: { root: "local", parts: ["optional"] },
            value: null,
          },
        ],
      },
      decodeDraftWorkspace,
    );
  });

  it("sets output bindings with an exact ordered copy, including empty lists", async () => {
    const { executor: writeExecutor, run } = createExecutor();
    const client = createDraftAuthoringClient(writeExecutor);
    const bindings = [
      { source: "text", target: "state.report" },
      { source: "text", target: "state.audit.latest" },
    ] satisfies SetStepOutputBindingsInput["bindings"];
    const input = {
      workspaceId: "report",
      revision: 7,
      stepId: "render",
      bindings,
    } satisfies SetStepOutputBindingsInput;

    await client.setStepOutputBindings(input);
    expect(run).toHaveBeenCalledWith(
      "workflow.draft_workspaces.set_step_output_bindings",
      {
        workspace_id: "report",
        revision: 7,
        step_id: "render",
        bindings: [
          { source: "text", target: "state.report" },
          { source: "text", target: "state.audit.latest" },
        ],
      },
      decodeDraftWorkspace,
    );
    bindings.splice(0, bindings.length);
    expect(run).toHaveBeenCalledWith(
      "workflow.draft_workspaces.set_step_output_bindings",
      {
        workspace_id: "report",
        revision: 7,
        step_id: "render",
        bindings: [
          { source: "text", target: "state.report" },
          { source: "text", target: "state.audit.latest" },
        ],
      },
      decodeDraftWorkspace,
    );

    await client.setStepOutputBindings({ ...input, bindings: [] });
    expect(run).toHaveBeenLastCalledWith(
      "workflow.draft_workspaces.set_step_output_bindings",
      {
        workspace_id: "report",
        revision: 7,
        step_id: "render",
        bindings: [],
      },
      decodeDraftWorkspace,
    );
  });

  it("rejects blank identifiers for focused binding methods before transport", async () => {
    const { executor: writeExecutor, run } = createExecutor();
    const client = createDraftAuthoringClient(writeExecutor);
    const input = {
      workspaceId: "report",
      revision: 7,
      stepId: "render",
      bindings: [],
    } satisfies SetStepOutputBindingsInput;

    await expect(client.setStepInputBindings({ ...input, workspaceId: " " })).rejects.toMatchObject({
      kind: "operation",
      operation: "workflow.draft_workspaces.set_step_input_bindings",
    });
    await expect(client.setStepOutputBindings({ ...input, stepId: "\t" })).rejects.toMatchObject({
      kind: "operation",
      operation: "workflow.draft_workspaces.set_step_output_bindings",
    });
    expect(run).not.toHaveBeenCalled();
  });

  it("deeply copies input binding records, paths, and JSON values", async () => {
    const { executor: writeExecutor, run } = createExecutor();
    const client = createDraftAuthoringClient(writeExecutor);
    const pathBinding = {
      path: { root: "context", parts: ["request", "text"] },
      target: { root: "local", parts: ["text"] },
    } satisfies InputPathBinding;
    const valueBinding = {
      target: { root: "local", parts: ["optional"] },
      value: { nested: ["keep"] },
    } satisfies InputValueBinding;
    const bindings = [pathBinding, valueBinding] satisfies SetStepInputBindingsInput["bindings"];

    await client.setStepInputBindings({
      workspaceId: "report",
      revision: 7,
      stepId: "render",
      bindings,
    });

    if (typeof pathBinding.path !== "string") pathBinding.path.parts[0] = "changed";
    if (typeof pathBinding.target !== "string") pathBinding.target.parts[0] = "changed";
    pathBinding.path = { root: "context", parts: ["changed.path"] };
    pathBinding.target = { root: "local", parts: ["changed.target"] };
    valueBinding.target.parts[0] = "changed";
    valueBinding.value.nested[0] = "changed";
    expect(run).toHaveBeenCalledWith(
      "workflow.draft_workspaces.set_step_input_bindings",
      {
        workspace_id: "report",
        revision: 7,
        step_id: "render",
        bindings: [
          {
            path: { root: "context", parts: ["request", "text"] },
            target: { root: "local", parts: ["text"] },
          },
          {
            target: { root: "local", parts: ["optional"] },
            value: { nested: ["keep"] },
          },
        ],
      },
      decodeDraftWorkspace,
    );
  });

  it("deeply copies output binding records and structural paths", async () => {
    const { executor: writeExecutor, run } = createExecutor();
    const client = createDraftAuthoringClient(writeExecutor);
    const outputBinding = {
      source: { root: "local", parts: ["text"] },
      target: { root: "state", parts: ["report", "latest"] },
    } satisfies OutputBinding;
    const bindings = [outputBinding] satisfies SetStepOutputBindingsInput["bindings"];

    await client.setStepOutputBindings({
      workspaceId: "report",
      revision: 7,
      stepId: "render",
      bindings,
    });

    if (typeof outputBinding.source !== "string") outputBinding.source.parts[0] = "changed";
    if (typeof outputBinding.target !== "string") outputBinding.target.parts[0] = "changed";
    outputBinding.source = { root: "local", parts: ["changed.source"] };
    outputBinding.target = { root: "state", parts: ["changed.target"] };
    expect(run).toHaveBeenCalledWith(
      "workflow.draft_workspaces.set_step_output_bindings",
      {
        workspace_id: "report",
        revision: 7,
        step_id: "render",
        bindings: [
          {
            source: { root: "local", parts: ["text"] },
            target: { root: "state", parts: ["report", "latest"] },
          },
        ],
      },
      decodeDraftWorkspace,
    );
  });

  it("preserves recursive expression bindings when sending node-local inputs", async () => {
    const { executor: writeExecutor, run } = createExecutor();
    const client = createDraftAuthoringClient(writeExecutor);
    const bindings = [
      {
        target: "request",
        expression: {
          kind: "object",
          fields: {
            items: {
              kind: "array",
              items: [
                { kind: "path", path: "state.foo" },
                { kind: "literal", value: "wowcool" },
              ],
            },
            separator: { kind: "literal", value: " " },
          },
        },
      },
    ] satisfies ReadonlyArray<StepInputBinding>;

    await client.setStepInputBindings({
      workspaceId: "report",
      revision: 7,
      stepId: "concat",
      bindings,
    });

    expect(run).toHaveBeenCalledWith(
      "workflow.draft_workspaces.set_step_input_bindings",
      {
        workspace_id: "report",
        revision: 7,
        step_id: "concat",
        bindings,
      },
      decodeDraftWorkspace,
    );
    const sentParams = run.mock.calls[0]?.[1] as {
      readonly bindings: ReadonlyArray<StepInputBinding>;
    };
    const sourceBinding = bindings[0];
    const sentBinding = sentParams.bindings[0];
    if (sourceBinding === undefined || sentBinding === undefined) {
      throw new Error("expected the recursive binding to be sent");
    }
    expect(sentParams.bindings).not.toBe(bindings);
    expect(sentBinding).not.toBe(sourceBinding);
    if (!("expression" in sourceBinding) || !("expression" in sentBinding)) {
      throw new Error("expected an expression binding");
    }
    expect(sentBinding.expression).not.toBe(sourceBinding.expression);
  });
});

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  generateWorkflowContractSource,
  parseWorkflowContractManifest,
} from "./workflow-contract-generator.js";

const packageRoot = fileURLToPath(new URL("..", import.meta.url));
const repositoryRoot = fileURLToPath(new URL("../../../..", import.meta.url));

const fixture = {
  manifest_version: 1,
  source: { format: "openrpc", openrpc_version: "1.2.6" },
  components: {
    errors: {},
    schemas: {
      HealthResult: {
        additionalProperties: false,
        properties: { status: { const: "ok", type: "string" } },
        required: ["status"],
        type: "object",
      },
      JsonValue: {
        anyOf: [
          { type: "boolean" },
          { type: "integer" },
          { type: "number" },
          { type: "string" },
          {
            items: { $ref: "#/components/schemas/JsonValue" },
            type: "array",
          },
          {
            additionalProperties: { $ref: "#/components/schemas/JsonValue" },
            type: "object",
          },
          { type: "null" },
        ],
      },
      InputPathBinding: {
        additionalProperties: false,
        properties: {
          path: { type: "string" },
          target: { type: "string" },
        },
        required: ["path", "target"],
        type: "object",
      },
      InputValueBinding: {
        additionalProperties: false,
        properties: {
          target: { type: "string" },
          value: { $ref: "#/components/schemas/JsonValue" },
        },
        required: ["target", "value"],
        type: "object",
      },
      StepInputBinding: {
        anyOf: [
          { $ref: "#/components/schemas/InputPathBinding" },
          { $ref: "#/components/schemas/InputValueBinding" },
        ],
      },
      OutputBinding: {
        additionalProperties: false,
        properties: {
          source: { type: "string" },
          target: { type: "string" },
        },
        required: ["source", "target"],
        type: "object",
      },
      DraftWorkspaceResult: {
        additionalProperties: false,
        properties: { workspace_id: { type: "string" } },
        required: ["workspace_id"],
        type: "object",
      },
      FailureResult: {
        additionalProperties: false,
        properties: { message: { type: "string" } },
        required: ["message"],
        type: "object",
      },
    },
  },
  operations: [
    {
      action: "inspect",
      errors: [],
      method: "workflow.widgets.inspect",
      namespace: ["workflow", "widgets"],
      params: [
        {
          name: "widget_id",
          required: true,
          schema: { minLength: 1, type: "string" },
        },
        {
          name: "verbose",
          required: false,
          schema: { type: "boolean" },
        },
        {
          name: "note",
          required: false,
          schema: { anyOf: [{ type: "string" }, { type: "null" }] },
        },
        {
          name: "filter",
          required: false,
          schema: {
            additionalProperties: false,
            properties: { kind: { type: "string" } },
            required: ["kind"],
            type: "object",
          },
        },
        {
          name: "metadata",
          required: false,
          schema: { additionalProperties: true, type: "object" },
        },
      ],
      result: {
        schema: {
          anyOf: [
            { $ref: "#/components/schemas/HealthResult" },
            { $ref: "#/components/schemas/FailureResult" },
          ],
        },
      },
    },
    {
      action: "health",
      errors: [],
      method: "workflow.health",
      namespace: ["workflow"],
      params: [],
      result: { schema: { $ref: "#/components/schemas/HealthResult" } },
    },
  ],
};
const fixtureManifest = JSON.stringify(fixture);

const runtimeOperationNames = [
  "workflow.health",
  "workflow.sources.list",
  "workflow.capabilities.call",
  "workflow.capabilities.list",
  "workflow.capabilities.inspect",
  "workflow.draft_workspaces.add_step_from_capability",
  "workflow.draft_workspaces.create_empty",
  "workflow.draft_workspaces.create_from_capability",
  "workflow.draft_workspaces.list",
  "workflow.draft_workspaces.get",
  "workflow.draft_workspaces.set_route",
  "workflow.draft_workspaces.set_step_input_bindings",
  "workflow.draft_workspaces.set_step_output_bindings",
  "workflow.draft_workspaces.update_capability_step",
  "workflow.draft_workspaces.validate",
  "workflow.artifacts.list",
  "workflow.artifacts.inspect",
  "workflow.deployments.list",
  "workflow.deployments.inspect",
  "workflow.deployments.validate",
  "workflow.runs.list",
  "workflow.runs.inspect",
  "workflow.runs.start",
  "workflow.runs.resume",
  "workflow.runs.trace",
] as const;

const completeRuntimeFixture = {
  ...fixture,
  operations: [
    ...runtimeOperationNames.map((method) =>
      method === "workflow.draft_workspaces.set_step_input_bindings"
        ? {
            method,
            params: [
              {
                name: "bindings",
                required: true,
                schema: {
                  items: { $ref: "#/components/schemas/StepInputBinding" },
                  type: "array",
                },
              },
            ],
            result: {
              schema: { $ref: "#/components/schemas/DraftWorkspaceResult" },
            },
          }
        : method === "workflow.draft_workspaces.set_step_output_bindings"
          ? {
              method,
              params: [
                {
                  name: "bindings",
                  required: true,
                  schema: {
                    items: { $ref: "#/components/schemas/OutputBinding" },
                    type: "array",
                  },
                },
              ],
              result: {
                schema: { $ref: "#/components/schemas/DraftWorkspaceResult" },
              },
            }
          : {
              method,
              params: [],
              result: { schema: { $ref: "#/components/schemas/HealthResult" } },
            },
    ),
    ...fixture.operations.filter(({ method }) => method !== "workflow.health"),
  ],
};

describe("workflow contract generator", () => {
  it("generates lexical operation inventory and raw params/result maps", async () => {
    const source = await generateWorkflowContractSource(
      JSON.stringify(completeRuntimeFixture),
    );

    expect(source.indexOf('"workflow.health"')).toBeLessThan(
      source.indexOf('"workflow.widgets.inspect"'),
    );
    expect(source).toContain("widget_id: string");
    expect(source).toContain("verbose?: boolean");
    expect(source).toContain("note?: string | null");
    expect(source).toMatch(/filter\?: \{\s+kind: string;/);
    expect(source).toMatch(/metadata\?: \{\s+\[k: string\]: unknown;/);
    expect(source).toContain("params: Record<string, never>");
    expect(source).toContain("result: HealthResult | FailureResult");
    expect(source).toContain("value: JsonValue;");
    expect(source).toContain(
      "export type WorkflowOperationParams<Name extends WorkflowOperationName>",
    );
    expect(source).toContain(
      "export type WorkflowOperationResult<Name extends WorkflowOperationName>",
    );
    expect(source).not.toMatch(/\bany\b/);
  });

  it("embeds only reachable runtime schemas for the selected RPC cohort", async () => {
    const source = await generateWorkflowContractSource(
      JSON.stringify(completeRuntimeFixture),
    );
    const runtimeSource = source.slice(
      source.indexOf("export const workflowRuntimeContract"),
    );

    expect(runtimeSource).toContain('"workflow.health"');
    expect(runtimeSource).toContain('"HealthResult"');
    expect(runtimeSource).toContain('"JsonValue"');
    expect(runtimeSource).toContain('"additionalProperties": false');
    expect(runtimeSource).toContain('"properties": {}');
    expect(runtimeSource).not.toContain('"workflow.widgets.inspect"');
    expect(runtimeSource).not.toContain('"FailureResult"');
  });

  it("preserves oneOf when runtime branches can overlap", async () => {
    const overlapping = {
      ...completeRuntimeFixture,
      components: {
        ...completeRuntimeFixture.components,
        schemas: {
          ...completeRuntimeFixture.components.schemas,
          HealthResult: {
            additionalProperties: false,
            properties: {
              status: {
                oneOf: [
                  { minLength: 1, type: "string" },
                  { const: "ok", type: "string" },
                ],
              },
            },
            required: ["status"],
            type: "object",
          },
        },
      },
    };

    const source = await generateWorkflowContractSource(JSON.stringify(overlapping));
    const runtimeSource = source.slice(source.indexOf("export const workflowRuntimeContract"));

    expect(runtimeSource).toContain('"oneOf": [');
  });

  it("rejects a manifest missing a configured runtime operation", async () => {
    const reduced = {
      ...completeRuntimeFixture,
      operations: completeRuntimeFixture.operations.filter(
        ({ method }) => method !== "workflow.runs.resume",
      ),
    };

    await expect(
      generateWorkflowContractSource(JSON.stringify(reduced)),
    ).rejects.toThrow(/missing runtime operation.*workflow\.runs\.resume/i);
  });

  it("requires draft authoring operations in the runtime cohort", async () => {
    const reduced = {
      ...completeRuntimeFixture,
      operations: completeRuntimeFixture.operations.filter(
        ({ method }) => method !== "workflow.draft_workspaces.validate",
      ),
    };

    await expect(
      generateWorkflowContractSource(JSON.stringify(reduced)),
    ).rejects.toThrow(/missing runtime operation.*workflow\.draft_workspaces\.validate/i);
  });

  it.each([
    "workflow.draft_workspaces.set_step_input_bindings",
    "workflow.draft_workspaces.set_step_output_bindings",
  ])("rejects a manifest missing focused operation %s", async (method) => {
    const reduced = {
      ...completeRuntimeFixture,
      operations: completeRuntimeFixture.operations.filter(
        (operation) => operation.method !== method,
      ),
    };
    const escapedMethod = method.replaceAll(".", "\\.");

    await expect(
      generateWorkflowContractSource(JSON.stringify(reduced)),
    ).rejects.toThrow(
      new RegExp(`missing runtime operation.*${escapedMethod}`, "i"),
    );
  });

  it("includes focused binding operations and reachable binding schemas", async () => {
    const source = await generateWorkflowContractSource(
      JSON.stringify(completeRuntimeFixture),
    );
    const runtimeSource = source.slice(
      source.indexOf("export const workflowRuntimeContract"),
    );

    expect(runtimeSource).toContain(
      '"workflow.draft_workspaces.set_step_input_bindings"',
    );
    expect(runtimeSource).toContain(
      '"workflow.draft_workspaces.set_step_output_bindings"',
    );
    expect(runtimeSource).toContain('"InputPathBinding"');
    expect(runtimeSource).toContain('"InputValueBinding"');
    expect(runtimeSource).toContain('"StepInputBinding"');
    expect(runtimeSource).toContain('"OutputBinding"');
  });

  it("rejects non-local references reachable from the runtime cohort", async () => {
    const externalReference = {
      ...completeRuntimeFixture,
      operations: completeRuntimeFixture.operations.map((operation) =>
        operation.method === "workflow.health"
          ? { ...operation, result: { schema: { $ref: "https://example.com/schema" } } }
          : operation,
      ),
    };

    await expect(
      generateWorkflowContractSource(JSON.stringify(externalReference)),
    ).rejects.toThrow(/external runtime schema reference/i);
  });

  it("rejects duplicate operation methods", () => {
    const [firstOperation] = fixture.operations;
    if (firstOperation === undefined) throw new Error("invalid test fixture");
    const duplicate = {
      ...fixture,
      operations: [...fixture.operations, firstOperation],
    };

    expect(() => parseWorkflowContractManifest(JSON.stringify(duplicate))).toThrow(
      /duplicate operation method workflow\.widgets\.inspect/i,
    );
  });

  it("rejects duplicate parameter names before object projection", () => {
    const [firstOperation] = fixture.operations;
    const [firstParam] = firstOperation?.params ?? [];
    if (firstOperation === undefined || firstParam === undefined) {
      throw new Error("invalid test fixture");
    }
    const duplicate = {
      ...fixture,
      operations: [
        {
          ...firstOperation,
          params: [...firstOperation.params, firstParam],
        },
        ...fixture.operations.slice(1),
      ],
    };

    expect(() => parseWorkflowContractManifest(JSON.stringify(duplicate))).toThrow(
      /duplicate parameter name widget_id.*workflow\.widgets\.inspect/i,
    );
  });

  it("matches the checked generated contract for all server operations", async () => {
    const manifestText = await readFile(
      `${repositoryRoot}/contracts/workflow-api.manifest.json`,
      "utf8",
    );
    const checkedSource = await readFile(
      `${packageRoot}/src/generated/workflow-contract.ts`,
      "utf8",
    );

    const generatedSource = await generateWorkflowContractSource(manifestText);
    expect(generatedSource).toBe(checkedSource);
    expect(generatedSource.match(/^  \| "workflow\./gm)).toHaveLength(70);
  });
});

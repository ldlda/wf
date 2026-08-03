import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { compileFromFile } from "json-schema-to-typescript";
import { Schema } from "effect";

type JsonPrimitive = boolean | null | number | string;
type JsonValue = JsonPrimitive | JsonValue[] | { readonly [key: string]: JsonValue };
type JsonObject = { readonly [key: string]: JsonValue };

interface WorkflowContractParam {
  readonly name: string;
  readonly required: boolean;
  readonly schema: JsonObject;
}

interface WorkflowContractOperation {
  readonly method: string;
  readonly params: readonly WorkflowContractParam[];
  readonly resultSchema: JsonObject;
}

export interface WorkflowContractManifest {
  readonly manifestVersion: 1;
  readonly schemas: JsonObject;
  readonly operations: readonly WorkflowContractOperation[];
}

const decodeJson = Schema.decodeUnknownSync(Schema.parseJson(Schema.Unknown));

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const jsonValueAt = (value: unknown, path: string): JsonValue => {
  if (
    value === null ||
    typeof value === "boolean" ||
    typeof value === "number" ||
    typeof value === "string"
  ) {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item, index) => jsonValueAt(item, `${path}[${index}]`));
  }
  if (isRecord(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        jsonValueAt(item, `${path}.${key}`),
      ]),
    );
  }
  throw new Error(`${path} must contain only JSON values`);
};

const objectAt = (value: unknown, path: string): JsonObject => {
  if (!isRecord(value)) throw new Error(`${path} must be an object`);
  const decoded = jsonValueAt(value, path);
  if (Array.isArray(decoded) || decoded === null || typeof decoded !== "object") {
    throw new Error(`${path} must be an object`);
  }
  return decoded;
};

const arrayAt = (value: unknown, path: string): readonly unknown[] => {
  if (!Array.isArray(value)) throw new Error(`${path} must be an array`);
  return value;
};

const stringAt = (value: unknown, path: string): string => {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${path} must be a non-empty string`);
  }
  return value;
};

const booleanAt = (value: unknown, path: string): boolean => {
  if (typeof value !== "boolean") throw new Error(`${path} must be a boolean`);
  return value;
};

const compareText = (left: string, right: string): number =>
  left < right ? -1 : left > right ? 1 : 0;

export const parseWorkflowContractManifest = (
  manifestText: string,
): WorkflowContractManifest => {
  const value = decodeJson(manifestText);
  if (!isRecord(value)) throw new Error("workflow contract manifest must be an object");
  if (value.manifest_version !== 1) {
    throw new Error("workflow contract manifest_version must be 1");
  }

  const components = objectAt(value.components, "components");
  const schemas = objectAt(components.schemas, "components.schemas");
  const methods = new Set<string>();
  const operations = arrayAt(value.operations, "operations")
    .map((operationValue, operationIndex): WorkflowContractOperation => {
      if (!isRecord(operationValue)) {
        throw new Error(`operations[${operationIndex}] must be an object`);
      }
      const method = stringAt(
        operationValue.method,
        `operations[${operationIndex}].method`,
      );
      if (methods.has(method)) throw new Error(`duplicate operation method ${method}`);
      methods.add(method);

      const parameterNames = new Set<string>();
      const params = arrayAt(
        operationValue.params,
        `operations[${operationIndex}].params`,
      ).map((paramValue, paramIndex): WorkflowContractParam => {
        if (!isRecord(paramValue)) {
          throw new Error(
            `operations[${operationIndex}].params[${paramIndex}] must be an object`,
          );
        }
        const name = stringAt(
          paramValue.name,
          `operations[${operationIndex}].params[${paramIndex}].name`,
        );
        if (parameterNames.has(name)) {
          throw new Error(`duplicate parameter name ${name} in ${method}`);
        }
        parameterNames.add(name);
        return {
          name,
          required: booleanAt(
            paramValue.required,
            `operations[${operationIndex}].params[${paramIndex}].required`,
          ),
          schema: objectAt(
            paramValue.schema,
            `operations[${operationIndex}].params[${paramIndex}].schema`,
          ),
        };
      });

      const result = objectAt(
        operationValue.result,
        `operations[${operationIndex}].result`,
      );
      return {
        method,
        params,
        resultSchema: objectAt(
          result.schema,
          `operations[${operationIndex}].result.schema`,
        ),
      };
    })
    .sort((left, right) => compareText(left.method, right.method));

  return { manifestVersion: 1, schemas, operations };
};

const rewriteComponentRefs = (value: JsonValue): JsonValue => {
  if (Array.isArray(value)) return value.map(rewriteComponentRefs);
  if (value === null || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      key === "$ref" && typeof item === "string"
        ? item.replace("#/components/schemas/", "#/definitions/")
        : rewriteComponentRefs(item),
    ]),
  );
};

const paramsSchemaFor = (operation: WorkflowContractOperation): JsonObject =>
  operation.params.length === 0
    ? {
        // TypeScript's `{}` accepts every non-nullish value; this preserves an empty RPC object.
        tsType: "Record<string, never>",
      }
    : {
        additionalProperties: false,
        properties: Object.fromEntries(
          operation.params.map((param) => [
            param.name,
            rewriteComponentRefs(param.schema),
          ]),
        ),
        required: operation.params
          .filter((param) => param.required)
          .map((param) => param.name),
        type: "object",
      };

const compilerSchemaFor = (manifest: WorkflowContractManifest): JsonObject => ({
  additionalProperties: false,
  definitions: rewriteComponentRefs(manifest.schemas),
  properties: Object.fromEntries(
    manifest.operations.map((operation) => [
      operation.method,
      {
        additionalProperties: false,
        properties: {
          params: paramsSchemaFor(operation),
          result: rewriteComponentRefs(operation.resultSchema),
        },
        required: ["params", "result"],
        type: "object",
      },
    ]),
  ),
  required: manifest.operations.map((operation) => operation.method),
  title: "WorkflowContractMap",
  type: "object",
});

const compileSchema = async (schema: JsonObject): Promise<string> => {
  const temporaryDirectory = await mkdtemp(join(tmpdir(), "workflow-contract-"));
  const schemaPath = join(temporaryDirectory, "workflow-contract.schema.json");
  try {
    // compileFromFile owns JSON Schema parsing, avoiding a second handwritten schema AST.
    await writeFile(schemaPath, `${JSON.stringify(schema, null, 2)}\n`, "utf8");
    return await compileFromFile(schemaPath, {
      bannerComment: "",
      format: true,
      unknownAny: true,
      unreachableDefinitions: true,
    });
  } finally {
    await rm(temporaryDirectory, { force: true, recursive: true });
  }
};

const inventorySource = (operationNames: readonly string[]): string => {
  const union = operationNames.map((name) => `  | ${JSON.stringify(name)}`).join("\n");
  const values = operationNames.map((name) => `  ${JSON.stringify(name)},`).join("\n");
  return [
    "// Generated by `pnpm contract:write`. Do not edit by hand.",
    "// These are compile-time wire types, not runtime decoders or authorization.",
    "",
    "export type WorkflowOperationName =",
    `${union};`,
    "",
    "export const workflowOperationNames: readonly WorkflowOperationName[] = [",
    values,
    "];",
    "",
  ].join("\n");
};

export const generateWorkflowContractSource = async (
  manifestText: string,
): Promise<string> => {
  const manifest = parseWorkflowContractManifest(manifestText);
  const compiled = await compileSchema(compilerSchemaFor(manifest));
  const helpers = [
    "",
    "export type WorkflowOperationParams<Name extends WorkflowOperationName> =",
    '  WorkflowContractMap[Name]["params"];',
    "",
    "export type WorkflowOperationResult<Name extends WorkflowOperationName> =",
    '  WorkflowContractMap[Name]["result"];',
    "",
  ].join("\n");
  return `${inventorySource(manifest.operations.map(({ method }) => method))}${compiled.trim()}\n${helpers}`;
};

export const writeWorkflowContract = async (
  manifestPath: string,
  outputPath: string,
): Promise<void> => {
  const manifestText = await readFile(manifestPath, "utf8");
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, await generateWorkflowContractSource(manifestText), "utf8");
};

export const checkWorkflowContract = async (
  manifestPath: string,
  outputPath: string,
): Promise<void> => {
  const [manifestText, checkedSource] = await Promise.all([
    readFile(manifestPath, "utf8"),
    readFile(outputPath, "utf8"),
  ]);
  const generatedSource = await generateWorkflowContractSource(manifestText);
  if (generatedSource !== checkedSource) {
    throw new Error("generated workflow contract is stale; run `pnpm contract:write`");
  }
};

import { describe, expect, it } from "vitest";
import { normalizeSchema, rebaseSchemaField, schemaFieldAtPath } from "./schema-field.js";

describe("normalizeSchema", () => {
  it("normalizes primitive, multiline, boolean, and enum fields", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        name: { type: "string", title: "Display name", description: "Shown to users." },
        notes: { type: "string", format: "textarea" },
        count: { type: "number" },
        retries: { type: "integer" },
        enabled: { type: "boolean", default: true },
        color: { enum: ["red", 2, false, null] },
      },
      required: ["name", "enabled"],
    });

    expect(field.kind).toBe("object");
    expect(field.children.map((child) => [child.key, child.kind, child.required])).toEqual([
      ["name", "string", true],
      ["notes", "string", false],
      ["count", "number", false],
      ["retries", "integer", false],
      ["enabled", "boolean", true],
      ["color", "enum", false],
    ]);
    expect(field.children[0]).toMatchObject({
      path: ["name"],
      title: "Display name",
      description: "Shown to users.",
    });
    expect(field.children[4]).toMatchObject({
      hasDefault: true,
      defaultValue: true,
    });
    expect(field.children[5]?.enumValues).toEqual(["red", 2, false, null]);
  });

  it("normalizes nested objects and arrays with item fields", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        profile: {
          type: "object",
          properties: {
            age: { type: "integer" },
          },
          required: ["age"],
        },
        tags: { type: "array", items: { type: "string" } },
      },
    });

    const profile = field.children[0];
    const tags = field.children[1];
    expect(profile?.children[0]).toMatchObject({
      path: ["profile", "age"],
      key: "age",
      required: true,
      kind: "integer",
    });
    expect(tags).toMatchObject({ path: ["tags"], kind: "array" });
    expect(tags?.item).toMatchObject({ path: ["tags", 0], kind: "string" });
  });

  it("preserves an explicit null default", () => {
    const field = normalizeSchema({
      type: "object",
      properties: { value: { type: "string", default: null } },
    });

    expect(field.children[0]).toMatchObject({
      hasDefault: true,
      defaultValue: null,
    });
  });

  it("uses JSON fallback for unconstrained schemas instead of inventing an object", () => {
    const field = normalizeSchema({});

    expect(field).toMatchObject({ kind: "json", path: [], children: [], item: null });
    expect(field.fallbackReason).toBe("The schema is unconstrained; edit JSON directly.");
  });

  it("uses field-local fallback reasons for unsupported unions and references", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        choice: { oneOf: [{ type: "string" }, { type: "number" }] },
        reference: { $ref: "#/definitions/Missing" },
      },
    });

    expect(field.children[0]).toMatchObject({
      kind: "json",
      fallbackReason: "The schema uses oneOf, which the native form cannot represent.",
    });
    expect(field.children[1]).toMatchObject({
      kind: "json",
      fallbackReason: "Local schema reference target was not found.",
    });
  });

  it("projects the local ref in the wf.source.read_resource input schema", () => {
    const field = normalizeSchema({
      $defs: {
        SourceResourceRef: {
          description:
            "Workflow-safe resource handle. Only explicit source-aware helper nodes dereference it.",
          properties: {
            kind: {
              const: "source_resource_ref",
              default: "source_resource_ref",
              title: "Kind",
              type: "string",
            },
            logical_source: { minLength: 1, title: "Logical Source", type: "string" },
            uri: { minLength: 1, title: "Uri", type: "string" },
            mime_type: {
              anyOf: [{ type: "string" }, { type: "null" }],
              default: null,
              title: "Mime Type",
            },
            name: {
              anyOf: [{ type: "string" }, { type: "null" }],
              default: null,
              title: "Name",
            },
          },
          required: ["logical_source", "uri"],
          title: "SourceResourceRef",
          type: "object",
        },
      },
      description: "Input model for wf.source.read_resource node.",
      properties: {
        ref: { $ref: "#/$defs/SourceResourceRef" },
        max_chars: {
          default: 4000,
          maximum: 20000,
          minimum: 1,
          title: "Max Chars",
          type: "integer",
        },
      },
      required: ["ref"],
      title: "ReadResourceInput",
      type: "object",
    });

    const ref = field.children.find((child) => child.key === "ref");
    expect(ref).toMatchObject({ kind: "object", required: true });
    expect(ref?.children.map((child) => child.key)).toEqual([
      "kind",
      "logical_source",
      "uri",
      "mime_type",
      "name",
    ]);
    expect(ref?.children.find((child) => child.key === "logical_source")).toMatchObject({
      kind: "string",
      required: true,
    });
    expect(ref?.children.find((child) => child.key === "uri")).toMatchObject({
      kind: "string",
      required: true,
    });
    expect(ref?.children.find((child) => child.key === "kind")).toMatchObject({
      kind: "string",
      hasDefault: true,
      defaultValue: "source_resource_ref",
    });
  });

  it("falls back deterministically for an object reference cycle through a property", () => {
    const field = normalizeSchema({
      $defs: {
        Node: {
          type: "object",
          properties: {
            label: { type: "string" },
            child: { $ref: "#/$defs/Node" },
          },
        },
      },
      type: "object",
      properties: {
        root: { $ref: "#/$defs/Node" },
      },
    });

    const root = field.children.find((child) => child.key === "root");
    const child = root?.children.find((candidate) => candidate.key === "child");
    expect(child).toMatchObject({
      kind: "json",
      fallbackReason: "Local schema reference cycle detected.",
    });
  });

  it("falls back deterministically for an array reference cycle through its items", () => {
    const field = normalizeSchema({
      $defs: {
        RecursiveList: {
          type: "array",
          items: { $ref: "#/$defs/RecursiveList" },
        },
      },
      type: "object",
      properties: {
        values: { $ref: "#/$defs/RecursiveList" },
      },
    });

    const values = field.children.find((child) => child.key === "values");
    expect(values).toMatchObject({ kind: "array" });
    expect(values?.item).toMatchObject({
      kind: "json",
      fallbackReason: "Local schema reference cycle detected.",
    });
  });

  it("allows independent sibling fields to reuse the same referenced schema", () => {
    const field = normalizeSchema({
      $defs: {
        Shared: {
          type: "object",
          properties: { value: { type: "string" } },
        },
      },
      type: "object",
      properties: {
        first: { $ref: "#/$defs/Shared" },
        second: { $ref: "#/$defs/Shared" },
      },
    });

    expect(field.children.map((child) => child.kind)).toEqual([
      "object",
      "object",
    ]);
    expect(field.children.map((child) => child.children[0]?.kind)).toEqual([
      "string",
      "string",
    ]);
  });

  it("recursively rebases nested object and array item paths", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        items: {
          type: "array",
          items: {
            type: "object",
            properties: {
              profile: {
                type: "object",
                properties: { name: { type: "string" } },
              },
            },
          },
        },
      },
    });
    const item = field.children[0]?.item;
    expect(item).not.toBeNull();
    if (!item) return;

    const rebased = rebaseSchemaField(item, ["items", 1]);
    expect(rebased.path).toEqual(["items", 1]);
    expect(rebased.children[0]?.path).toEqual(["items", 1, "profile"]);
    expect(rebased.children[0]?.children[0]?.path).toEqual([
      "items",
      1,
      "profile",
      "name",
    ]);
  });

  it("looks up nested object, array, root, and missing schema paths", () => {
    const root = normalizeSchema({
      type: "object",
      properties: {
        profile: {
          type: "object",
          properties: { name: { type: "string" } },
        },
        items: { type: "array", items: { type: "integer" } },
      },
    });

    expect(schemaFieldAtPath(root, [])).toBe(root);
    expect(schemaFieldAtPath(root, ["profile", "name"])).toMatchObject({
      key: "name",
      kind: "string",
      path: ["profile", "name"],
    });
    expect(schemaFieldAtPath(root, ["items", 2])).toMatchObject({
      key: "item",
      kind: "integer",
      path: ["items", 2],
    });
    expect(schemaFieldAtPath(root, ["missing"])).toBeNull();
  });
});

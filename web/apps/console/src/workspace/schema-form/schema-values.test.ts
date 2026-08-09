import { describe, expect, it } from "vitest";
import { normalizeSchema } from "./schema-field.js";
import { serializeSchemaValues, type FieldSources } from "./schema-values.js";

describe("serializeSchemaValues", () => {
  it("omits empty optional values but preserves required incomplete fields and defaults", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        requiredName: { type: "string" },
        optionalNote: { type: "string" },
        withDefault: { type: "string", default: null },
      },
      required: ["requiredName"],
    });

    const result = serializeSchemaValues(field, {
      requiredName: "",
      optionalNote: "",
    });

    expect(result.value).toEqual({ requiredName: "", withDefault: null });
    expect(result.issues).toEqual([
      { path: ["requiredName"], message: "Required field is incomplete." },
    ]);
  });

  it("parses primitive controls and preserves nested paths", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        count: { type: "number" },
        retries: { type: "integer" },
        enabled: { type: "boolean" },
        profile: {
          type: "object",
          properties: { score: { type: "number" } },
        },
        tags: { type: "array", items: { type: "integer" } },
      },
    });

    const result = serializeSchemaValues(field, {
      count: "2.5",
      retries: "3",
      enabled: "false",
      profile: { score: "4.25" },
      tags: ["1", "2"],
    });

    expect(result.value).toEqual({
      count: 2.5,
      retries: 3,
      enabled: false,
      profile: { score: 4.25 },
      tags: [1, 2],
    });
    expect(result.issues).toEqual([]);
  });

  it("serializes valid nested bindings separately from literal values", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        title: { type: "string" },
        profile: {
          type: "object",
          properties: { email: { type: "string" } },
        },
      },
    });
    const sources: FieldSources = {
      "profile.email": { mode: "bind", sourcePath: "input.user.email" },
    };

    const result = serializeSchemaValues(field, { title: "Report" }, sources);

    expect(result.value).toEqual({ title: "Report", profile: {} });
    expect(result.bindings).toEqual([
      { target: "profile.email", path: "input.user.email" },
    ]);
    expect(result.literalBindings).toEqual([
      { target: "title", value: "Report" },
    ]);
    expect(result.issues).toEqual([]);
  });

  it("lowers root, nested, array, and null literals without wrappers", () => {
    const objectResult = serializeSchemaValues(
      normalizeSchema({
        type: "object",
        properties: {
          profile: {
            type: "object",
            properties: { display: { type: "string" } },
          },
          tags: { type: "array", items: { type: "string" } },
          note: { type: "string" },
        },
      }),
      { profile: { display: "Ada" }, tags: ["one", "two"], note: null },
    );
    const rootResult = serializeSchemaValues(normalizeSchema({ type: "array", items: { type: "string" } }), ["one"]);

    expect(objectResult.literalBindings).toEqual([
      { target: "profile.display", value: "Ada" },
      { target: "tags.0", value: "one" },
      { target: "tags.1", value: "two" },
      { target: "note", value: null },
    ]);
    expect(rootResult.literalBindings).toEqual([{ target: "0", value: "one" }]);
  });

  it("returns a field-local issue for malformed binding paths without throwing", () => {
    const field = normalizeSchema({
      type: "object",
      properties: { title: { type: "string" } },
      required: ["title"],
    });
    const sources: FieldSources = {
      title: { mode: "bind", sourcePath: "not a workflow path" },
    };

    const result = serializeSchemaValues(field, { title: "Report" }, sources);

    expect(result.value).toEqual({ title: undefined });
    expect(result.bindings).toEqual([]);
    expect(result.issues).toEqual([
      { path: ["title"], message: "Binding path must start with input, state, or context." },
    ]);
  });

  it("formats and validates quoted TOML-key paths, including the root marker", () => {
    const nestedField = normalizeSchema({
      type: "object",
      properties: {
        profile: {
          type: "object",
          properties: { "display.name": { type: "string" } },
        },
      },
    });
    const nestedResult = serializeSchemaValues(
      nestedField,
      { profile: {} },
      {
        'profile."display.name"': {
          mode: "bind",
          sourcePath: 'input."user.name"',
        },
      },
    );
    const rootResult = serializeSchemaValues(
      normalizeSchema({ type: "string" }),
      "literal",
      { ".": { mode: "bind", sourcePath: "input.payload" } },
    );

    expect(nestedResult.bindings).toEqual([
      { target: 'profile."display.name"', path: 'input."user.name"' },
    ]);
    expect(nestedResult.issues).toEqual([]);
    expect(rootResult.bindings).toEqual([{ target: ".", path: "input.payload" }]);
  });

  it("rejects whitespace-only quoted binding path segments", () => {
    const field = normalizeSchema({ type: "string" });
    const result = serializeSchemaValues(field, "literal", {
      ".": { mode: "bind", sourcePath: 'input."   "' },
    });

    expect(result.bindings).toEqual([]);
    expect(result.issues).toEqual([
      { path: [], message: "Binding path must start with input, state, or context." },
    ]);
  });

  it("does not alias a nested path with a literal dotted property", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        "a.b": { type: "string" },
        a: { type: "object", properties: { b: { type: "string" } } },
      },
    });

    const result = serializeSchemaValues(
      field,
      { "a.b": "initial dotted", a: { b: "initial nested" } },
      { "a.b": { mode: "literal", value: "canonical nested" } },
    );

    expect(result.value).toEqual({ "a.b": "initial dotted", a: { b: "canonical nested" } });
  });

  it("rebases bindings for the second nested object array item", () => {
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
    const result = serializeSchemaValues(
      field,
      { items: [{ profile: {} }, { profile: {} }] },
      {
        "items.1.profile.name": { mode: "bind", sourcePath: "input.second" },
      },
    );

    expect(result.bindings).toEqual([
      { target: "items.1.profile.name", path: "input.second" },
    ]);
    expect(result.issues).toEqual([]);
  });

  it("preserves absence versus explicit false for optional booleans", () => {
    const field = normalizeSchema({
      type: "object",
      properties: { enabled: { type: "boolean" } },
    });

    expect(serializeSchemaValues(field, {}).value).toEqual({});
    expect(serializeSchemaValues(field, { enabled: false }).value).toEqual({ enabled: false });
  });

  it("requires an explicit true or false value for a required boolean without a default", () => {
    const field = normalizeSchema({
      type: "object",
      properties: { enabled: { type: "boolean" } },
      required: ["enabled"],
    });

    expect(serializeSchemaValues(field, { enabled: undefined }).issues).toEqual([
      { path: ["enabled"], message: "Choose true or false." },
    ]);
    expect(serializeSchemaValues(field, { enabled: true })).toMatchObject({
      value: { enabled: true },
      issues: [],
    });
    expect(serializeSchemaValues(field, { enabled: false })).toMatchObject({
      value: { enabled: false },
      issues: [],
    });
  });

  it("reports and preserves missing required string and JSON values", () => {
    const field = normalizeSchema({
      type: "object",
      properties: {
        name: { type: "string" },
        payload: {},
      },
      required: ["name", "payload"],
    });
    const result = serializeSchemaValues(field, {});

    expect(result.value).toEqual({ name: "", payload: "" });
    expect(result.issues).toEqual([
      { path: ["name"], message: "Required field is incomplete." },
      { path: ["payload"], message: "Required field is incomplete." },
    ]);
  });

  it("preserves an explicit empty object default", () => {
    const field = normalizeSchema({
      type: "object",
      properties: { options: { type: "object", default: {}, properties: {} } },
    });

    expect(serializeSchemaValues(field, {}).value).toEqual({ options: {} });
  });

  it("keeps enum values distinct when their display text collides", () => {
    const field = normalizeSchema({
      type: "object",
      properties: { choice: { enum: ["true", true, "1", 1] } },
    });

    expect(serializeSchemaValues(field, { choice: true }).value).toEqual({ choice: true });
    expect(serializeSchemaValues(field, { choice: 1 }).value).toEqual({ choice: 1 });
  });
});

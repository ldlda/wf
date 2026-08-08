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
    expect(result.issues).toEqual([]);
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
});

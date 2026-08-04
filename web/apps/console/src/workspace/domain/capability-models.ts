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

const JsonObjectSchema = v.record(v.string(), v.unknown());
const WrapperHintsSchema = v.record(v.string(), v.unknown());

const CapabilitySummarySchema = v.variant("kind", [
  v.object({
    kind: v.literal("node_spec"),
    name: v.string(),
    sourceId: v.string(),
    description: v.nullish(v.string(), null),
    outcomes: v.array(v.string()),
    inputFields: v.array(v.string()),
    outputFields: v.array(v.string()),
  }),
  v.object({
    kind: v.literal("wrapper_artifact"),
    name: v.string(),
    sourceId: v.string(),
    description: v.nullish(v.string(), null),
    outcomes: v.array(v.string()),
    inputFields: v.array(v.string()),
    outputFields: v.array(v.string()),
  }),
]);

const CapabilityPageSchema = v.object({
  capabilities: v.array(CapabilitySummarySchema),
  nextCursor: v.nullish(v.string(), null),
  total: v.number(),
});

const CapabilityDetailSchema = v.variant("kind", [
  v.object({
    kind: v.literal("node_spec"),
    name: v.string(),
    sourceId: v.string(),
    description: v.nullish(v.string(), null),
    isAsync: v.boolean(),
    outcomes: v.array(v.string()),
    inputSchema: JsonObjectSchema,
    outputSchema: JsonObjectSchema,
    wrapperHints: WrapperHintsSchema,
    acceptsContext: v.boolean(),
  }),
  v.object({
    kind: v.literal("wrapper_artifact"),
    name: v.string(),
    sourceId: v.string(),
    description: v.nullish(v.string(), null),
    isAsync: v.boolean(),
    outcomes: v.array(v.string()),
    inputSchema: JsonObjectSchema,
    outputSchema: JsonObjectSchema,
    wrapperHints: WrapperHintsSchema,
    artifactId: v.string(),
    title: v.string(),
    version: v.number(),
    requiredCapabilities: v.record(v.string(), v.unknown()),
  }),
]);

export type CapabilitySummary = v.InferOutput<typeof CapabilitySummarySchema>;
export type CapabilityPage = v.InferOutput<typeof CapabilityPageSchema>;
export type CapabilityDetail = v.InferOutput<typeof CapabilityDetailSchema>;

export const decodeCapabilityPage = (value: unknown): CapabilityPage =>
  decode("CapabilityPage", CapabilityPageSchema, value);

export const decodeCapabilityDetail = (value: unknown): CapabilityDetail =>
  decode("CapabilityDetail", CapabilityDetailSchema, value);

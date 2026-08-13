const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export const MAX_INPUT_EXPRESSION_NODES = 1024;

const expressionKinds = new Set(["literal", "path", "array", "object"]);

/** Count expression nodes and containers nested inside literal values. */
export const hasBoundedInputExpressionNodeBudget = (
  input: unknown,
  maxNodes: number = MAX_INPUT_EXPRESSION_NODES,
): boolean => {
  let nodes = 0;
  const active = new WeakSet<object>();

  const visitNode = (value: object): boolean => {
    if (active.has(value)) return false;
    active.add(value);
    nodes += 1;
    if (nodes > maxNodes) {
      active.delete(value);
      return false;
    }
    return true;
  };

  const visitJson = (value: unknown): boolean => {
    if (typeof value !== "object" || value === null) return true;
    if (!visitNode(value)) return false;
    const valid = Array.isArray(value)
      ? value.every(visitJson)
      : Object.values(value).every(visitJson);
    active.delete(value);
    return valid;
  };

  const visitExpression = (value: unknown): boolean => {
    if (!isRecord(value) || typeof value.kind !== "string") return false;
    if (!expressionKinds.has(value.kind) || !visitNode(value)) return false;

    let valid = true;
    switch (value.kind) {
      case "literal":
        valid = visitJson(value.value);
        break;
      case "path":
        break;
      case "array":
        valid = Array.isArray(value.items) && value.items.every(visitExpression);
        break;
      case "object":
        valid = isRecord(value.fields) && Object.values(value.fields).every(visitExpression);
        break;
    }
    active.delete(value);
    return valid;
  };

  return visitExpression(input);
};

type JsonSchemaRecord = Readonly<Record<string, unknown>>;

const schemaRecord = (value: unknown): JsonSchemaRecord | null =>
  isRecord(value) ? value : null;

const localComponentName = (ref: unknown): string | null => {
  if (typeof ref !== "string") return null;
  const prefix = "#/components/schemas/";
  return ref.startsWith(prefix) ? ref.slice(prefix.length) : null;
};

/**
 * Bound only expression bindings found through a generated operation schema.
 *
 * This deliberately follows schema positions instead of inspecting arbitrary
 * JSON for expression-shaped objects. Ordinary runtime data can use the same
 * `kind`/`value` keys without becoming an input expression.
 */
export const hasBoundedInputExpressionsAtSchema = (
  input: unknown,
  schema: unknown,
  components: Readonly<Record<string, unknown>>,
  maxNodes: number = MAX_INPUT_EXPRESSION_NODES,
): boolean => {
  const activeValues = new WeakSet<object>();
  const activeComponents = new Set<string>();

  const visit = (value: unknown, currentSchema: unknown): boolean => {
    const schemaValue = schemaRecord(currentSchema);
    if (schemaValue === null) return true;

    const componentName = localComponentName(schemaValue.$ref);
    if (componentName !== null) {
      if (componentName === "StepInputBinding" || componentName === "InputExpressionBinding") {
        return isRecord(value) && "expression" in value
          ? hasBoundedInputExpressionNodeBudget(value.expression, maxNodes)
          : true;
      }
      const component = components[componentName];
      if (component === undefined || activeComponents.has(componentName)) return true;
      activeComponents.add(componentName);
      const valid = visit(value, component);
      activeComponents.delete(componentName);
      return valid;
    }

    for (const key of ["allOf", "anyOf", "oneOf"] as const) {
      const branches = schemaValue[key];
      if (Array.isArray(branches) && !branches.every((branch) => visit(value, branch))) {
        return false;
      }
    }

    if (typeof value !== "object" || value === null) return true;
    if (activeValues.has(value)) return false;
    activeValues.add(value);

    const properties = schemaRecord(schemaValue.properties);
    if (properties !== null && isRecord(value)) {
      for (const [key, propertySchema] of Object.entries(properties)) {
        if (key in value && !visit(value[key], propertySchema)) {
          activeValues.delete(value);
          return false;
        }
      }
    }

    const items = schemaValue.items;
    if (Array.isArray(value) && items !== undefined) {
      for (const item of value) {
        if (!visit(item, items)) {
          activeValues.delete(value);
          return false;
        }
      }
    }

    const additionalProperties = schemaValue.additionalProperties;
    if (isRecord(value) && schemaRecord(additionalProperties) !== null) {
      const knownProperties = properties === null ? new Set<string>() : new Set(Object.keys(properties));
      for (const [key, propertyValue] of Object.entries(value)) {
        if (!knownProperties.has(key) && !visit(propertyValue, additionalProperties)) {
          activeValues.delete(value);
          return false;
        }
      }
    }

    activeValues.delete(value);
    return true;
  };

  return visit(input, schema);
};

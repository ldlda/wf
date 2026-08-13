const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export const MAX_INPUT_EXPRESSION_NODES = 1024;
export const MAX_INPUT_EXPRESSION_DEPTH = 64;

const expressionKinds = new Set(["literal", "path", "array", "object"]);

type Budget = {
  nodes: number;
  readonly active: WeakSet<object>;
};

const newBudget = (nodes = 0): Budget => ({ nodes, active: new WeakSet<object>() });

const visitJsonValue = (
  value: unknown,
  depth: number,
  budget: Budget,
  maxNodes: number,
): boolean => {
  if (value === null || typeof value === "boolean" || typeof value === "string") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value !== "object") return false;
  if (depth > MAX_INPUT_EXPRESSION_DEPTH || budget.active.has(value)) return false;
  if (Array.isArray(value)) {
    if (Object.getOwnPropertySymbols(value).length > 0) return false;
    if (!Object.keys(value).every((key) => /^(0|[1-9]\d*)$/.test(key))) return false;
  } else if (
    (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null) ||
    Object.getOwnPropertySymbols(value).length > 0
  ) {
    return false;
  }

  budget.active.add(value);
  budget.nodes += 1;
  if (budget.nodes > maxNodes) {
    budget.active.delete(value);
    return false;
  }

  let valid = true;
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      if (!Object.prototype.hasOwnProperty.call(value, index) || !visitJsonValue(value[index], depth + 1, budget, maxNodes)) {
        valid = false;
        break;
      }
    }
  } else {
    for (const item of Object.values(value)) {
      if (!visitJsonValue(item, depth + 1, budget, maxNodes)) {
        valid = false;
        break;
      }
    }
  }
  budget.active.delete(value);
  return valid;
};

/**
 * Validate a JSON literal as the value of a depth-one literal expression.
 * The expression node consumes one budget slot, so containers begin at depth
 * two and the same node/depth rules apply as the Python/RPC boundary.
 */
export const hasBoundedInputExpressionLiteralValue = (
  value: unknown,
  maxNodes: number = MAX_INPUT_EXPRESSION_NODES,
): boolean => {
  if (maxNodes < 1) return false;
  return visitJsonValue(value, 2, newBudget(1), maxNodes);
};

/** Count expression nodes and containers nested inside literal values. */
export const hasBoundedInputExpressionNodeBudget = (
  input: unknown,
  maxNodes: number = MAX_INPUT_EXPRESSION_NODES,
): boolean => {
  const budget = newBudget();

  const visitNode = (value: object): boolean => {
    if (budget.active.has(value)) return false;
    budget.active.add(value);
    budget.nodes += 1;
    if (budget.nodes > maxNodes) {
      budget.active.delete(value);
      return false;
    }
    return true;
  };

  const visitExpression = (value: unknown, depth: number): boolean => {
    if (depth > MAX_INPUT_EXPRESSION_DEPTH) return false;
    if (!isRecord(value) || typeof value.kind !== "string") return false;
    if (!expressionKinds.has(value.kind) || !visitNode(value)) return false;

    let valid = true;
    switch (value.kind) {
      case "literal":
        // The literal branch shares the strict JSON traversal used by simple
        // bindings while continuing the expression node budget.
        valid = visitJsonValue(value.value, depth + 1, budget, maxNodes);
        break;
      case "path":
        break;
      case "array":
        {
          const items = value.items;
          if (!Array.isArray(items)) {
            valid = false;
            break;
          }
          for (let index = 0; index < items.length; index += 1) {
            if (!Object.prototype.hasOwnProperty.call(items, index) || !visitExpression(items[index], depth + 1)) {
              valid = false;
              break;
            }
          }
        }
        break;
      case "object":
        {
          const fields = value.fields;
          if (!isRecord(fields)) {
            valid = false;
            break;
          }
          for (const item of Object.values(fields)) {
            if (!visitExpression(item, depth + 1)) {
              valid = false;
              break;
            }
          }
        }
        break;
    }
    budget.active.delete(value);
    return valid;
  };

  return visitExpression(input, 1);
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

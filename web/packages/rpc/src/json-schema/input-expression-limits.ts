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

/** Find and bound generated expression-shaped values anywhere in an RPC value. */
export const hasBoundedInputExpressionPayload = (
  input: unknown,
  maxNodes: number = MAX_INPUT_EXPRESSION_NODES,
): boolean => {
  const active = new WeakSet<object>();
  const visit = (value: unknown): boolean => {
    if (typeof value !== "object" || value === null) return true;
    if (active.has(value)) return false;
    active.add(value);
    const valid = Array.isArray(value)
      ? value.every(visit)
      : isRecord(value) &&
        (typeof value.kind === "string" &&
        expressionKinds.has(value.kind) &&
        ((value.kind === "literal" && "value" in value) ||
          (value.kind === "path" && "path" in value) ||
          (value.kind === "array" && Array.isArray(value.items)) ||
          (value.kind === "object" && isRecord(value.fields)))
          ? hasBoundedInputExpressionNodeBudget(value, maxNodes)
          : Object.values(value).every(visit));
    active.delete(value);
    return valid;
  };

  return visit(input);
};

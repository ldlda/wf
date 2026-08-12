import type { DraftDiagnostic } from "../domain/draft-workspace-models.js";

export type DiagnosticEntry = {
  readonly diagnostic: DraftDiagnostic;
  readonly key: string;
};

const isRecord = (value: unknown): value is Readonly<Record<string, unknown>> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const canonicalize = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (!isRecord(value)) return value;
  return Object.fromEntries(
    Object.entries(value)
      .toSorted(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => [key, canonicalize(item)]),
  );
};

const diagnosticIdentity = (diagnostic: DraftDiagnostic): string =>
  JSON.stringify([
    diagnostic.code,
    diagnostic.path,
    diagnostic.message,
    diagnostic.stepId,
    diagnostic.repairHint,
    canonicalize(diagnostic.details),
  ]);

export const withDiagnosticKeys = (
  diagnostics: ReadonlyArray<DraftDiagnostic>,
): ReadonlyArray<DiagnosticEntry> => {
  const seenIdentities = new Set<string>();
  const entries: DiagnosticEntry[] = [];
  for (const diagnostic of diagnostics) {
    const identity = diagnosticIdentity(diagnostic);
    if (seenIdentities.has(identity)) {
      continue;
    }
    seenIdentities.add(identity);
    entries.push({
      diagnostic,
      key: `diagnostic-${identity}`,
    });
  }
  return entries;
};

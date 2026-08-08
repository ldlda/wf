import type { DraftDiagnostic } from "../domain/draft-workspace-models.js";

export type DiagnosticEntry = {
  readonly diagnostic: DraftDiagnostic;
  readonly key: string;
};

const diagnosticIdentity = (diagnostic: DraftDiagnostic): string =>
  JSON.stringify([
    diagnostic.code,
    diagnostic.path,
    diagnostic.message,
    diagnostic.stepId,
    diagnostic.repairHint,
    diagnostic.details,
  ]);

export const withDiagnosticKeys = (
  diagnostics: ReadonlyArray<DraftDiagnostic>,
): ReadonlyArray<DiagnosticEntry> => {
  const occurrenceByIdentity = new Map<string, number>();
  const entries: DiagnosticEntry[] = [];
  for (const diagnostic of diagnostics) {
    const identity = diagnosticIdentity(diagnostic);
    const occurrence = occurrenceByIdentity.get(identity) ?? 0;
    occurrenceByIdentity.set(identity, occurrence + 1);
    entries.push({
      diagnostic,
      key: `diagnostic-${identity}-${occurrence}`,
    });
  }
  return entries;
};

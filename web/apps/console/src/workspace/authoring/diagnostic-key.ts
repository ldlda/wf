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

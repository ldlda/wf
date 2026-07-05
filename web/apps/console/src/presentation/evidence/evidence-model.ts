import type { EvidenceRecord } from "../../app/state.js";

export type EvidenceReceiptModel = {
  readonly available: boolean;
  readonly operation: string;
  readonly status: string | null;
  readonly recordCount: number;
};

export type EvidenceDetailModel = EvidenceReceiptModel & {
  readonly id: string;
  readonly label: string;
  readonly equivalentCli: string;
  readonly durationMs: number;
  readonly deploymentId: string | null;
  readonly runId: string | null;
  readonly request: FormattedEvidenceValue;
  readonly response: FormattedEvidenceValue;
};

export type FormattedEvidenceValue = {
  readonly text: string;
  readonly note: string | null;
};

const MAX_EVIDENCE_TEXT_LENGTH = 100_000;

// Guarded object helper: reads nested properties without assuming the full
// response shape or casting the complete payload.
const objectValue = (value: unknown): Readonly<Record<string, unknown>> | null =>
  typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Readonly<Record<string, unknown>>
    : null;

const responseStatus = (response: unknown): string | null => {
  const result = objectValue(objectValue(response)?.result);
  return typeof result?.status === "string" ? result.status : null;
};

const stringField = (
  value: Readonly<Record<string, unknown>> | null,
  field: string,
): string | null => {
  const candidate = value?.[field];
  return typeof candidate === "string" ? candidate : null;
};

const boundEvidenceText = (
  text: string,
  note: string | null,
): FormattedEvidenceValue => {
  if (text.length <= MAX_EVIDENCE_TEXT_LENGTH) return { text, note };
  const truncation = `Evidence truncated to ${MAX_EVIDENCE_TEXT_LENGTH} characters.`;
  return {
    text: `${text.slice(0, MAX_EVIDENCE_TEXT_LENGTH)}...`,
    note: note ? `${note} ${truncation}` : truncation,
  };
};

export const formatEvidenceValue = (value: unknown): FormattedEvidenceValue => {
  try {
    const encoded = JSON.stringify(value, null, 2);
    return boundEvidenceText(encoded ?? String(value), null);
  } catch {
    let text: string;
    try {
      text = String(value);
    } catch {
      text = "[Unprintable evidence]";
    }
    return boundEvidenceText(
      text,
      "Could not format as JSON; showing a bounded text representation.",
    );
  }
};

export const projectEvidenceReceipt = (
  records: readonly EvidenceRecord[],
): EvidenceReceiptModel => {
  const latest = records.at(-1);
  if (!latest) {
    return { available: false, operation: "Evidence unavailable", status: null, recordCount: 0 };
  }
  return {
    available: true,
    operation: latest.operation,
    status: responseStatus(latest.response),
    recordCount: records.length,
  };
};

export const projectEvidenceDetail = (record: EvidenceRecord): EvidenceDetailModel => {
  const request = objectValue(record.request);
  const result = objectValue(objectValue(record.response)?.result);
  return {
    ...projectEvidenceReceipt([record]),
    id: record.id,
    label: record.label,
    equivalentCli: record.equivalentCli,
    durationMs: record.durationMs,
    deploymentId: stringField(result, "deployment_id") ?? stringField(request, "deployment_id"),
    runId: stringField(result, "run_id") ?? stringField(request, "run_id"),
    request: formatEvidenceValue(record.request),
    response: formatEvidenceValue(record.response),
  };
};

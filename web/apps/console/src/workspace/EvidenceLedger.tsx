import type { EvidenceRecord } from "../app/state.js";

type Props = {
  readonly records: ReadonlyArray<EvidenceRecord>;
};

const formatValue = (value: unknown): string => {
  const formatted = JSON.stringify(value, null, 2);
  return formatted === undefined ? String(value) : formatted;
};

export const EvidenceLedger = ({ records }: Props) => (
  <div className="evidence-ledger">
    {records.length === 0 ? (
      <p className="empty-state">No operation evidence yet.</p>
    ) : (
      <ol className="evidence-list">
        {records.map((record) => (
          <li key={record.id}>
            <details className="evidence-record" aria-label={record.label}>
              <summary>
                <span className="evidence-op">{record.operation}</span>
                <span className="evidence-label">{record.label}</span>
                <span className="evidence-duration">{record.durationMs}ms</span>
              </summary>
              <dl className="evidence-detail">
                <div className="evidence-field">
                  <dt>Equivalent CLI</dt>
                  <dd><code>{record.equivalentCli}</code></dd>
                </div>
                <div className="evidence-field">
                  <dt>Request</dt>
                  <dd><pre>{formatValue(record.request)}</pre></dd>
                </div>
                <div className="evidence-field">
                  <dt>Response</dt>
                  <dd><pre>{formatValue(record.response)}</pre></dd>
                </div>
              </dl>
            </details>
          </li>
        ))}
      </ol>
    )}
  </div>
);

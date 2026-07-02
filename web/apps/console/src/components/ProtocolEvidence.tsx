import { useState } from "react";
import type { EvidenceRecord } from "../app/state.js";

type Props = {
  readonly evidence: ReadonlyArray<EvidenceRecord>;
};

export const ProtocolEvidence = ({ evidence }: Props) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggle = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <section aria-label="Protocol Evidence">
      <h2>Protocol Evidence</h2>
      {evidence.length === 0 ? (
        <p data-testid="evidence-empty">No evidence recorded yet.</p>
      ) : (
        <ul data-testid="evidence-list" className="evidence-list">
          {evidence.map((record) => (
            <li key={record.id}>
              <button
                type="button"
                aria-expanded={expandedId === record.id}
                data-testid={`evidence-toggle-${record.id}`}
                onClick={() => toggle(record.id)}
                className="evidence-toggle"
              >
                <span className="evidence-op">{record.operation}</span>
                <span className="evidence-label">{record.label}</span>
                <span className="evidence-duration">
                  {record.durationMs}ms
                </span>
              </button>
              {expandedId === record.id && (
                <div
                  data-testid={`evidence-detail-${record.id}`}
                  className="evidence-detail"
                >
                  <div className="evidence-field">
                    <h3>Equivalent CLI</h3>
                    <pre>
                      <code>{record.equivalentCli}</code>
                    </pre>
                  </div>
                  <div className="evidence-field">
                    <h3>Request</h3>
                    <pre>
                      <code>{JSON.stringify(record.request, null, 2)}</code>
                    </pre>
                  </div>
                  <div className="evidence-field">
                    <h3>Response</h3>
                    <pre>
                      <code>
                        {record.response !== null
                          ? JSON.stringify(record.response, null, 2)
                          : "No response received."}
                      </code>
                    </pre>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

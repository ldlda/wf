import type { EvidenceRecord } from "../app/state.js";
import { formatJson } from "./format.js";
import type { EvidencePresentation } from "./storyboard.js";

type EvidenceDrawerProps = {
  readonly records: readonly EvidenceRecord[];
  readonly mode: EvidencePresentation;
  readonly close: () => void;
};

export const EvidenceDrawer = ({ records, mode, close }: EvidenceDrawerProps) => {
  if (mode === "hidden") return null;

  return (
    <aside className="evidence-drawer" data-mode={mode} aria-label="presentation evidence">
      <header>
        <h2>Evidence</h2>
        <button type="button" onClick={close}>Close</button>
      </header>
      {records.length === 0 ? (
        <p>No live evidence captured in this view yet. Replay operation blocks still show recorded evidence.</p>
      ) : (
        records.map((record) => (
          <article key={record.id}>
            <h3>{record.operation}</h3>
            <p>{record.label}</p>
            <pre><code>{record.equivalentCli}</code></pre>
            <pre><code>{formatJson(record.response)}</code></pre>
          </article>
        ))
      )}
    </aside>
  );
};

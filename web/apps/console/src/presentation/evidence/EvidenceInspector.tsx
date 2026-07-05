import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { EvidenceRecord } from "../../app/state.js";
import { projectEvidenceDetail } from "./evidence-model.js";

type EvidenceInspectorProps = {
  readonly records: readonly EvidenceRecord[];
  readonly open: boolean;
  readonly onClose: () => void;
};

export const EvidenceInspector = ({
  records,
  open,
  onClose,
}: EvidenceInspectorProps) => {
  const [view, setView] = useState<"interpreted" | "raw">("interpreted");
  const [selectedRecordId, setSelectedRecordId] = useState(
    () => records.at(-1)?.id ?? "",
  );
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setSelectedRecordId((current) =>
      records.some((record) => record.id === current)
        ? current
        : records.at(-1)?.id ?? "",
    );
  }, [records]);

  const selectedRecord = records.find((record) => record.id === selectedRecordId)
    ?? records.at(-1)
    ?? null;
  const detail = selectedRecord ? projectEvidenceDetail(selectedRecord) : null;

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    closeButtonRef.current?.focus();
    return () => previouslyFocused?.focus();
  }, [open]);

  const trapTabWithinDialog = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== "Tab") return;
    const focusable = [...(dialogRef.current?.querySelectorAll<HTMLElement>(
      "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
    ) ?? [])].filter((element) => !element.hasAttribute("disabled"));
    const first = focusable.at(0);
    const last = focusable.at(-1);
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  if (!open) return null;

  return (
    <div className="evidence-inspector-layer">
      <section
        ref={dialogRef}
        className="evidence-inspector"
        role="dialog"
        aria-modal="true"
        aria-label="Evidence inspector"
        onKeyDown={trapTabWithinDialog}
      >
        <header>
          <h2>Evidence</h2>
          <button ref={closeButtonRef} type="button" onClick={onClose}>
            Close evidence
          </button>
        </header>
        {selectedRecord && (
          <label>
            Evidence record
            <select
              value={selectedRecord.id}
              onChange={(event) => setSelectedRecordId(event.currentTarget.value)}
            >
              {records.map((record) => (
                <option key={record.id} value={record.id}>{record.operation}</option>
              ))}
            </select>
          </label>
        )}
        <div role="tablist" aria-label="Evidence view">
          <button role="tab" aria-selected={view === "interpreted"} onClick={() => setView("interpreted")}>
            Interpreted
          </button>
          <button role="tab" aria-selected={view === "raw"} onClick={() => setView("raw")}>
            Raw
          </button>
        </div>
        <div className="evidence-inspector__body">
          {!detail ? (
            <p>Evidence unavailable</p>
          ) : view === "interpreted" ? (
            <dl>
              <dt>Operation</dt><dd>{detail.operation}</dd>
              <dt>Status</dt><dd>{detail.status ?? "Unavailable"}</dd>
              <dt>Duration</dt><dd>{detail.durationMs} ms</dd>
              <dt>Deployment</dt><dd>{detail.deploymentId ?? "Unavailable"}</dd>
              <dt>Run</dt><dd>{detail.runId ?? "Unavailable"}</dd>
            </dl>
          ) : (
            <>
              <h3>Equivalent CLI</h3><pre><code>{detail.equivalentCli}</code></pre>
              <h3>Request</h3><pre><code>{detail.request.text}</code></pre>
              {detail.request.note && <p>{detail.request.note}</p>}
              <h3>Response</h3><pre><code>{detail.response.text}</code></pre>
              {detail.response.note && <p>{detail.response.note}</p>}
            </>
          )}
        </div>
      </section>
    </div>
  );
};

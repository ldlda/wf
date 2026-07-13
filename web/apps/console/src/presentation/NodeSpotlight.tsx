import { useEffect, useRef, type KeyboardEvent } from "react";
import { presentationNodes } from "./workflow-graph-data.js";

type NodeSpotlightProps = {
  readonly nodeId: string;
  readonly close: () => void;
};

const kindLabel = (node: (typeof presentationNodes)[number]): string => {
  if (node.type === "interrupt") return "Human boundary";
  if (node.type === "end") return "Outcome";
  return "Action";
};

export const NodeSpotlight = ({ nodeId, close }: NodeSpotlightProps) => {
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const node = presentationNodes.find((candidate) => candidate.id === nodeId);
  const label = node && "label" in node
    ? node.label
    : nodeId === "review_issues"
      ? "Review issues"
      : nodeId;

  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    closeButtonRef.current?.focus();
    return () => previouslyFocused?.focus();
  }, []);

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key !== "Tab") return;
    const focusable = [...(dialogRef.current?.querySelectorAll<HTMLElement>(
      "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
    ) ?? [])].filter((element) => !element.hasAttribute("disabled"));
    if (focusable.length === 0) return;
    const first = focusable[0]!;
    const last = focusable[focusable.length - 1]!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  if (!node) return null;
  const schemaSummary = "schemaSummary" in node ? node.schemaSummary : null;

  return (
    <aside
      ref={dialogRef}
      className="node-spotlight"
      role="dialog"
      aria-modal="true"
      aria-label={label}
      data-node-kind={node.type}
      onKeyDown={handleKeyDown}
    >
      <header className="node-spotlight__header">
        <div>
          <p className="node-spotlight__eyebrow">Workflow node</p>
          <span className="node-spotlight__kind">{kindLabel(node)}</span>
        </div>
        <button type="button" ref={closeButtonRef} onClick={close}>Close</button>
      </header>
      <h2>{label}</h2>
      <p className="node-spotlight__detail">{node.detail}</p>

      <dl className="node-spotlight__facts">
        <div>
          <dt>Capability / boundary</dt>
          <dd>{node.capability}</dd>
        </div>
        <div>
          <dt>Input</dt>
          <dd>{node.inputSummary}</dd>
        </div>
        <div>
          <dt>Output</dt>
          <dd>{node.outputSummary}</dd>
        </div>
        {schemaSummary && (
          <div>
            <dt>Schema summary</dt>
            <dd>{schemaSummary}</dd>
          </div>
        )}
      </dl>

      <section className="node-spotlight__outcomes" aria-labelledby="node-spotlight-outcomes">
        <h3 id="node-spotlight-outcomes">Outcomes</h3>
        <ul>
          {node.outcomes.map((outcome) => <li key={outcome}>{outcome}</li>)}
        </ul>
      </section>

      <footer className="node-spotlight__evidence">
        <span>Code / evidence pointer</span>
        <code>{node.evidencePointer}</code>
      </footer>
    </aside>
  );
};

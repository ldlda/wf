import { useEffect, useRef, type KeyboardEvent } from "react";
import { presentationNodes } from "./workflow-graph-data.js";

type NodeSpotlightProps = {
  readonly nodeId: string;
  readonly close: () => void;
};

const nodeDescription = (nodeId: string): string => {
  if (nodeId === "review_issues") {
    return "Typed interrupt boundary. It exposes request and resume schemas, then waits for a submitted or cancelled outcome.";
  }
  if (nodeId === "create_issues") {
    return "Workflow step that writes selected review items into the local issue-board source.";
  }
  return "Prepared report workflow step. The presentation graph is curated, but each node maps back to workflow or run evidence.";
};

export const NodeSpotlight = ({ nodeId, close }: NodeSpotlightProps) => {
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const node = presentationNodes.find((candidate) => candidate.id === nodeId);
  const label = node && "label" in node
    ? node.label
    : node?.id === "review_issues"
      ? "Review issues"
      : node?.id ?? nodeId;

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

  return (
    <aside
      ref={dialogRef}
      className="node-spotlight"
      role="dialog"
      aria-modal="true"
      aria-label={label}
      onKeyDown={handleKeyDown}
    >
      <button type="button" ref={closeButtonRef} onClick={close}>Close</button>
      <p>Workflow node</p>
      <h2>{label}</h2>
      <p>{nodeDescription(node.id)}</p>
    </aside>
  );
};

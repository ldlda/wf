import { useEffect, useRef, type KeyboardEvent } from "react";
import { findDiscussionBranch, findScene } from "./storyboard.js";

type DiscussionPanelProps = {
  readonly branchId: string;
  readonly onClose: () => void;
};

export const DiscussionPanel = ({ branchId, onClose }: DiscussionPanelProps) => {
  const branch = findDiscussionBranch(branchId);
  const dialogRef = useRef<HTMLDivElement>(null);
  const returnButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!branch) return;
    const previouslyFocused = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    returnButtonRef.current?.focus();
    return () => previouslyFocused?.focus();
  }, [branch]);

  if (!branch) return null;

  const parentScene = findScene(branch.parentSceneId);

  const trapKeyboardWithinDialog = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
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

  return (
    <div
      ref={dialogRef}
      className="discussion-panel"
      role="dialog"
      aria-modal="true"
      aria-label={branch.title}
      onKeyDown={trapKeyboardWithinDialog}
    >
      <header>
        <h2>{branch.title}</h2>
        <span className="discussion-panel__badge">{branch.claimClass}</span>
      </header>
      <p className="discussion-panel__evidence">{branch.evidencePointer}</p>
      <p className="discussion-panel__summary">{branch.summary}</p>
      {branch.question && (
        <section className="discussion-panel__qna" aria-label="defense question">
          <p className="discussion-panel__question">{branch.question}</p>
          {branch.shortAnswer && (
            <p className="discussion-panel__short-answer">{branch.shortAnswer}</p>
          )}
          {branch.expandedAnswer && (
            <p className="discussion-panel__expanded-answer">{branch.expandedAnswer}</p>
          )}
          {branch.speakerHint && (
            <p className="discussion-panel__presenter-note" aria-label="presenter note">
              <span>Presenter note</span>
              {branch.speakerHint}
            </p>
          )}
        </section>
      )}
      {branch.detail && (
        <p className="discussion-panel__detail">
          {branch.detail.links?.map((link, index) => (
            <span key={link.href}>
              {index > 0 && " · "}
              <a href={link.href} target="_blank" rel="noopener noreferrer">{link.label}</a>
            </span>
          ))}
          {branch.detail.links && branch.detail.links.length > 0 ? " — " : ""}
          {branch.detail.text}
        </p>
      )}
      <button ref={returnButtonRef} type="button" onClick={onClose} className="discussion-panel__return">
        Return to {parentScene?.title ?? "scene"}
      </button>
    </div>
  );
};

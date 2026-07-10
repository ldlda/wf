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

  const hasQuestion = branch.question !== undefined;

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
      data-presentation-surface="editorial"
      data-discussion-layout={hasQuestion ? "qna" : "context"}
      role="dialog"
      aria-modal="true"
      aria-label={branch.title}
      onKeyDown={trapKeyboardWithinDialog}
    >
      <div className="discussion-panel__shell" aria-label="discussion shell">
        <header className="discussion-panel__header">
          <div>
            <span className="discussion-panel__badge">{branch.claimClass}</span>
            <h2>{branch.title}</h2>
          </div>
        </header>

        <main className="discussion-panel__body" aria-label="discussion body">
          {hasQuestion ? (
            <section className="discussion-panel__qna" aria-label="defense question">
              <p className="discussion-panel__question">{branch.question}</p>
              {branch.shortAnswer && (
                <article className="discussion-panel__answer-card" aria-label="short defense answer">
                  <span>Short answer</span>
                  <p>{branch.shortAnswer}</p>
                </article>
              )}
              {branch.expandedAnswer && (
                <article className="discussion-panel__answer-card discussion-panel__answer-card--expanded" aria-label="answer expansion">
                  <span>Expanded answer</span>
                  <p>{branch.expandedAnswer}</p>
                </article>
              )}
            </section>
          ) : (
            <section className="discussion-panel__context" aria-label="discussion context">
              <p>{branch.summary}</p>
              {branch.detail && (
                <div className="discussion-panel__detail" aria-label="additional context">
                  <p>
                    {branch.detail.links?.map((link, index) => (
                      <span key={link.href}>
                        {index > 0 && " · "}
                        <a href={link.href} target="_blank" rel="noopener noreferrer">{link.label}</a>
                      </span>
                    ))}
                    {branch.detail.links && branch.detail.links.length > 0 ? " — " : ""}
                    {branch.detail.text}
                  </p>
                </div>
              )}
            </section>
          )}
        </main>

        <aside className="discussion-panel__aside" aria-label="discussion support">
          <section className="discussion-panel__provenance" aria-label="answer provenance">
            <span>Evidence</span>
            <p>{branch.evidencePointer}</p>
          </section>
          {branch.speakerHint && (
            <aside className="discussion-panel__presenter-note" aria-label="presenter note">
              <span>Presenter note</span>
              <p>{branch.speakerHint}</p>
            </aside>
          )}
        </aside>

        <footer className="discussion-panel__actions" aria-label="discussion actions">
          <button ref={returnButtonRef} type="button" onClick={onClose} className="discussion-panel__return">
            Return to {parentScene?.title ?? "scene"}
          </button>
        </footer>
      </div>
    </div>
  );
};

import { useEffect, useState } from "react";
import { findDiscussionBranch } from "../storyboard.js";
import { PresenterNote } from "./PresenterNote.js";
import { PresenterShell } from "./PresenterShell.js";
import { presenterHashForNote, presenterNavigationFromHash } from "./presenter-navigation.js";
import "./presenter.css";

const readHash = () => presenterNavigationFromHash(window.location.hash);

export const PresenterRoute = () => {
  const [navigation, setNavigation] = useState(readHash);
  const [covered, setCovered] = useState<ReadonlySet<string>>(() => new Set());

  useEffect(() => {
    const syncHash = () => setNavigation(readHash());
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      const destination = event.key === "ArrowRight" ? navigation.next : event.key === "ArrowLeft" ? navigation.previous : null;
      if (!destination) return;
      event.preventDefault();
      window.location.hash = presenterHashForNote(destination);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigation.next, navigation.previous]);

  const currentKey = navigation.note ? `${navigation.note.sceneId}/${navigation.note.beatId}` : null;
  const discussion = navigation.location.kind === "discussion" ? findDiscussionBranch(navigation.location.branchId) : undefined;

  return (
    <PresenterShell current={navigation.note} covered={covered}>
      <div className="presenter-route__help" aria-label="Presenter keyboard help">← previous · → next · disclosures stay local</div>
      {navigation.note && (
        <PresenterNote
          note={navigation.note}
          cumulativeSeconds={navigation.cumulativeSeconds}
          next={navigation.next}
          covered={currentKey ? covered.has(currentKey) : false}
          onCoveredChange={(isCovered) => {
            if (!currentKey) return;
            setCovered((existing) => {
              const next = new Set(existing);
              if (isCovered) next.add(currentKey); else next.delete(currentKey);
              return next;
            });
          }}
        />
      )}
      {discussion && (
        <article className="presenter-qna" aria-labelledby="presenter-qna-title">
          <a href="#scene/thesis/title">Back to notes</a>
          <span>{discussion.claimClass}</span>
          <h1 id="presenter-qna-title">{discussion.question ?? discussion.title}</h1>
          <p className="presenter-qna__short">{discussion.shortAnswer ?? discussion.summary}</p>
          {discussion.expandedAnswer && <details><summary>Expanded answer</summary><p>{discussion.expandedAnswer}</p></details>}
          {discussion.speakerHint && <aside><strong>Presenter guidance</strong><p>{discussion.speakerHint}</p></aside>}
          <dl><dt>Evidence</dt><dd>{discussion.evidencePointer}</dd></dl>
        </article>
      )}
    </PresenterShell>
  );
};

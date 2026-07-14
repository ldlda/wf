import { findScene, mainScenes } from "../storyboard.js";
import { discussionBranchForId, type PresenterBeatNote } from "./presenter-notes.js";
import { audienceHrefForNote, formatPresenterTime, presenterHashForNote } from "./presenter-navigation.js";

type PresenterNoteProps = {
  readonly note: PresenterBeatNote;
  readonly cumulativeSeconds: number;
  readonly next: PresenterBeatNote | null;
  readonly covered: boolean;
  readonly onCoveredChange: (covered: boolean) => void;
};

export const PresenterNote = ({ note, cumulativeSeconds, next, covered, onCoveredChange }: PresenterNoteProps) => {
  const scene = findScene(note.sceneId);
  const sceneNumber = mainScenes.findIndex((candidate) => candidate.id === note.sceneId) + 1;
  return (
    <article className="presenter-note" aria-labelledby="presenter-note-title">
      <header className="presenter-note__header">
        <div>
          <span>Scene {sceneNumber || "?"} · {note.beatId}</span>
          <h1 id="presenter-note-title">{scene?.title ?? note.sceneId}</h1>
        </div>
        <div className="presenter-note__timing">
          <span>Target {formatPresenterTime(note.targetSeconds)}</span>
          <span>Cumulative {formatPresenterTime(cumulativeSeconds)}</span>
        </div>
      </header>

      <section className="presenter-note__goal" aria-labelledby="presenter-goal">
        <span id="presenter-goal">Beat goal</span>
        <div className="presenter-note__goal-copy"><ReactMarkdown>{note.goal}</ReactMarkdown></div>
      </section>

      <section className="presenter-note__anchors" aria-labelledby="presenter-anchors">
        <span id="presenter-anchors">Anchor terms</span>
        <ul>
          {note.keywords.map((keyword) => <li key={keyword}>{keyword}</li>)}
        </ul>
      </section>

      <section className="presenter-note__say" aria-labelledby="presenter-say">
        <span id="presenter-say">Suggested wording</span>
        <div className="presenter-note__markdown"><ReactMarkdown>{note.mustSay}</ReactMarkdown></div>
      </section>

      {note.warning && <aside className="presenter-note__warning"><strong>Warning</strong><p>{note.warning}</p></aside>}
      {note.fallback && <aside className="presenter-note__fallback"><strong>Fallback</strong><p>{note.fallback}</p></aside>}

      {note.optionalDetail && <details><summary>Optional detail</summary><p>{note.optionalDetail}</p></details>}
      <details>
        <summary>Evidence ({note.evidencePointers.length})</summary>
        <ul>{note.evidencePointers.map((pointer) => <li key={pointer}>{pointer}</li>)}</ul>
      </details>
      {note.qnaBranchIds.length > 0 && (
        <details>
          <summary>Linked Q&amp;A ({note.qnaBranchIds.length})</summary>
          <ul className="presenter-note__qna">
            {note.qnaBranchIds.map((branchId) => {
              const branch = discussionBranchForId(branchId);
              if (!branch) return null;
              return <li key={branchId}><a href={`#discuss/${branchId}`}>{branch.question ?? branch.title}</a></li>;
            })}
          </ul>
        </details>
      )}

      <footer className="presenter-note__actions">
        <label><input type="checkbox" checked={covered} onChange={(event) => onCoveredChange(event.target.checked)} /> Mark covered</label>
        <a href={audienceHrefForNote(note)} target="_blank" rel="noopener noreferrer">Open audience slide</a>
      </footer>

      {next && (
        <section className="presenter-note__next" aria-label="Next beat preview">
          <span>Next · {formatPresenterTime(next.targetSeconds)}</span>
          <div className="presenter-note__next-copy"><ReactMarkdown>{next.mustSay}</ReactMarkdown></div>
          <a href={presenterHashForNote(next)}>Go to next beat</a>
        </section>
      )}
    </article>
  );
};
import ReactMarkdown from "react-markdown";

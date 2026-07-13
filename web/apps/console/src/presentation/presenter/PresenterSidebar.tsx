import { discussionBranches, mainScenes, type DiscussionBranchId } from "../storyboard.js";
import { presenterSceneNotes, type PresenterBeatNote } from "./presenter-notes.js";
import { presenterHashForNote } from "./presenter-navigation.js";

type PresenterSidebarProps = {
  readonly current: PresenterBeatNote | null;
  readonly covered: ReadonlySet<string>;
  readonly activeDiscussionId: DiscussionBranchId | null;
};

export const PresenterSidebar = ({ current, covered, activeDiscussionId }: PresenterSidebarProps) => (
  <nav className="presenter-sidebar" aria-label="Presenter scene index">
    <a className="presenter-sidebar__brand" href="#scene/thesis/title">lda.chat defense</a>
    <details className="presenter-sidebar__qna" open={activeDiscussionId !== null}>
      <summary>Defense Q&amp;A <span>{discussionBranches.length}</span></summary>
      <ul>
        {discussionBranches.map((branch) => (
          <li key={branch.id}>
            <a
              href={`#discuss/${branch.id}`}
              aria-current={activeDiscussionId === branch.id ? "page" : undefined}
            >
              {"question" in branch && branch.question ? branch.question : branch.title}
            </a>
          </li>
        ))}
      </ul>
    </details>
    <ol>
      {mainScenes.map((scene, sceneIndex) => {
        const notes = presenterSceneNotes(scene.id);
        const active = current?.sceneId === scene.id;
        return (
          <li key={scene.id} data-active={active}>
            <span>{sceneIndex + 1}</span>
            <div>
              <strong>{scene.title}</strong>
              <div className="presenter-sidebar__beats">
                {notes.map((note, beatIndex) => (
                  <a
                    key={note.beatId}
                    href={presenterHashForNote(note)}
                    aria-current={current === note ? "page" : undefined}
                    data-covered={covered.has(`${note.sceneId}/${note.beatId}`)}
                  >
                    {beatIndex + 1}
                  </a>
                ))}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  </nav>
);

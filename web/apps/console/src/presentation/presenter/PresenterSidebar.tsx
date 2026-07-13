import { mainScenes } from "../storyboard.js";
import { presenterSceneNotes, type PresenterBeatNote } from "./presenter-notes.js";
import { presenterHashForNote } from "./presenter-navigation.js";

type PresenterSidebarProps = {
  readonly current: PresenterBeatNote | null;
  readonly covered: ReadonlySet<string>;
};

export const PresenterSidebar = ({ current, covered }: PresenterSidebarProps) => (
  <nav className="presenter-sidebar" aria-label="Presenter scene index">
    <a className="presenter-sidebar__brand" href="#scene/thesis/title">lda.chat defense</a>
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

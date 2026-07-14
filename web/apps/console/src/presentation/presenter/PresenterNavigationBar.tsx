import type { PresenterBeatNote } from "./presenter-notes.js";
import { presenterHashForNote } from "./presenter-navigation.js";
import { PresentationPairingPanel } from "../sync/PresentationPairingPanel.js";
import type { PresentationSyncController } from "../sync/presentation-sync-state.js";

type PresenterNavigationBarProps = {
  readonly currentIndex: number;
  readonly total: number;
  readonly previous: PresenterBeatNote | null;
  readonly next: PresenterBeatNote | null;
  readonly syncController: PresentationSyncController;
};

const DirectionLink = ({ note, children }: { readonly note: PresenterBeatNote | null; readonly children: string }) =>
  note
    ? <a href={presenterHashForNote(note)}>{children}</a>
    : <span aria-disabled="true">{children}</span>;

export const PresenterNavigationBar = ({ currentIndex, total, previous, next, syncController }: PresenterNavigationBarProps) => (
  <nav className="presenter-navigation" aria-label="Presenter note navigation">
    <DirectionLink note={previous}>← Previous</DirectionLink>
    <span>{currentIndex + 1} / {total}</span>
    <DirectionLink note={next}>Next →</DirectionLink>
    <PresentationPairingPanel role="presenter" controller={syncController} />
  </nav>
);

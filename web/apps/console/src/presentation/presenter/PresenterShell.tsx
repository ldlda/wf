import type { ReactNode } from "react";
import type { PresenterBeatNote } from "./presenter-notes.js";
import type { DiscussionBranchId } from "../storyboard.js";
import { PresenterSidebar } from "./PresenterSidebar.js";

type PresenterShellProps = {
  readonly current: PresenterBeatNote | null;
  readonly covered: ReadonlySet<string>;
  readonly activeDiscussionId: DiscussionBranchId | null;
  readonly children: ReactNode;
};

export const PresenterShell = ({ current, covered, activeDiscussionId, children }: PresenterShellProps) => (
  <main className="presenter-route" aria-label="lda.chat presenter notes">
    <PresenterSidebar current={current} covered={covered} activeDiscussionId={activeDiscussionId} />
    <div className="presenter-route__reader">{children}</div>
  </main>
);

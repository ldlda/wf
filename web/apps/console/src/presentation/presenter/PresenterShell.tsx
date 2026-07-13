import { useEffect, useRef, type ReactNode } from "react";
import { useDrag } from "@use-gesture/react";
import type { PresenterBeatNote } from "./presenter-notes.js";
import type { DiscussionBranchId } from "../storyboard.js";
import { PresenterSidebar } from "./PresenterSidebar.js";

type PresenterShellProps = {
  readonly current: PresenterBeatNote | null;
  readonly covered: ReadonlySet<string>;
  readonly activeDiscussionId: DiscussionBranchId | null;
  readonly onSwipeNext?: (() => void) | undefined;
  readonly onSwipePrevious?: (() => void) | undefined;
  readonly children: ReactNode;
};

const isInteractiveSwipeTarget = (event: Event): boolean =>
  event.target instanceof Element
  && event.target.closest("a, button, input, textarea, select, [role='button'], [contenteditable='true'], pre, code") !== null;

const RELEASE_DELTA_PX = 50;

export const PresenterShell = ({
  current,
  covered,
  activeDiscussionId,
  onSwipeNext,
  onSwipePrevious,
  children,
}: PresenterShellProps) => {
  const readerRef = useRef<HTMLDivElement>(null);
  const swipeStartedInInteractiveContent = useRef(false);
  const bindSwipe = useDrag(
    ({ event, first, last, movement: [deltaX, deltaY] }) => {
      if (!(event instanceof PointerEvent) || event.pointerType !== "touch") return;
      if (first) {
        swipeStartedInInteractiveContent.current = isInteractiveSwipeTarget(event);
      }
      if (!last || swipeStartedInInteractiveContent.current) return;
      if (Math.abs(deltaX) < RELEASE_DELTA_PX || Math.abs(deltaX) <= Math.abs(deltaY)) return;

      if (deltaX < 0) onSwipeNext?.();
      else onSwipePrevious?.();
    },
    {
      filterTaps: true,
      pointer: { capture: false },
      preventScroll: 0,
    },
  );

  useEffect(() => {
    // Let browser scroll restoration win; only skip the mobile index when this
    // is a genuinely fresh page load that remains at the top.
    const frame = window.requestAnimationFrame(() => {
      if (window.scrollY === 0) {
        readerRef.current?.scrollIntoView?.({ behavior: "auto", block: "start" });
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  return (
    <main className="presenter-route" aria-label="lda.chat presenter notes">
      <PresenterSidebar
        current={current}
        covered={covered}
        activeDiscussionId={activeDiscussionId}
      />
      <div
        {...bindSwipe()}
        ref={readerRef}
        className="presenter-route__reader"
      >
        {children}
      </div>
    </main>
  );
};

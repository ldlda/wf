import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PresenterShell } from "./PresenterShell.js";

class TestPointerEvent extends MouseEvent {
  readonly pointerId: number;
  readonly pointerType: string;

  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 0;
    this.pointerType = init.pointerType ?? "";
  }
}

beforeEach(() => {
  vi.stubGlobal("PointerEvent", TestPointerEvent);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const renderShell = ({
  onSwipeNext,
  onSwipePrevious,
}: {
  readonly onSwipeNext?: () => void;
  readonly onSwipePrevious?: () => void;
} = {}) =>
  render(
    <PresenterShell
      current={null}
      covered={new Set()}
      activeDiscussionId={null}
      onSwipeNext={onSwipeNext}
      onSwipePrevious={onSwipePrevious}
    >
      <p>Presenter content</p>
      <a href="#details">Details</a>
    </PresenterShell>,
  );

const swipe = (target: Element, fromX: number, toX: number, fromY = 20, toY = 20) => {
  fireEvent.pointerDown(target, {
    buttons: 1, clientX: fromX, clientY: fromY, pointerId: 1, pointerType: "touch",
  });
  fireEvent.pointerMove(target, {
    buttons: 1, clientX: toX, clientY: toY, pointerId: 1, pointerType: "touch",
  });
  fireEvent.pointerUp(target, {
    buttons: 0, clientX: toX, clientY: toY, pointerId: 1, pointerType: "touch",
  });
};

const reversingSwipe = (target: Element, points: readonly number[]) => {
  const [start, ...moves] = points;
  if (start === undefined || moves.length === 0) throw new Error("A swipe needs a start and release point");

  fireEvent.pointerDown(target, {
    buttons: 1, clientX: start, clientY: 20, pointerId: 1, pointerType: "touch",
  });
  for (const clientX of moves) {
    fireEvent.pointerMove(target, {
      buttons: 1, clientX, clientY: 20, pointerId: 1, pointerType: "touch",
    });
  }
  fireEvent.pointerUp(target, {
    buttons: 0, clientX: moves.at(-1), clientY: 20, pointerId: 1, pointerType: "touch",
  });
};

describe("PresenterShell", () => {
  it("reveals main content on a fresh page load", () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    vi.spyOn(window, "scrollY", "get").mockReturnValue(0);
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());

    renderShell();

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "auto", block: "start" });
  });

  it("preserves a restored or manual scroll position", () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    vi.spyOn(window, "scrollY", "get").mockReturnValue(240);
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());

    renderShell();

    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("navigates with deliberate horizontal touch swipes", () => {
    const onSwipeNext = vi.fn();
    const onSwipePrevious = vi.fn();
    const { container } = renderShell({ onSwipeNext, onSwipePrevious });
    const reader = container.querySelector(".presenter-route__reader");
    expect(reader).not.toBeNull();

    swipe(reader!, 180, 100);
    swipe(reader!, 100, 180);

    expect(onSwipeNext).toHaveBeenCalledTimes(1);
    expect(onSwipePrevious).toHaveBeenCalledTimes(1);
  });

  it("keeps vertical scrolling and interactive content out of swipe navigation", () => {
    const onSwipeNext = vi.fn();
    const { container } = renderShell({ onSwipeNext });
    const reader = container.querySelector(".presenter-route__reader");
    const link = container.querySelector("a[href='#details']");
    expect(reader).not.toBeNull();
    expect(link).not.toBeNull();

    swipe(reader!, 120, 110, 20, 120);
    swipe(link!, 180, 100);

    expect(onSwipeNext).not.toHaveBeenCalled();
  });

  it("uses final release displacement after a gesture reverses direction", () => {
    const onSwipeNext = vi.fn();
    const onSwipePrevious = vi.fn();
    const { container } = renderShell({ onSwipeNext, onSwipePrevious });
    const reader = container.querySelector(".presenter-route__reader");
    expect(reader).not.toBeNull();

    reversingSwipe(reader!, [160, 80, 240]);

    expect(onSwipeNext).not.toHaveBeenCalled();
    expect(onSwipePrevious).toHaveBeenCalledTimes(1);
  });

  it("does not navigate when a reversing gesture releases near its origin", () => {
    const onSwipeNext = vi.fn();
    const onSwipePrevious = vi.fn();
    const { container } = renderShell({ onSwipeNext, onSwipePrevious });
    const reader = container.querySelector(".presenter-route__reader");
    expect(reader).not.toBeNull();

    reversingSwipe(reader!, [160, 80, 165]);

    expect(onSwipeNext).not.toHaveBeenCalled();
    expect(onSwipePrevious).not.toHaveBeenCalled();
  });
});

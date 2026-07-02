# React Presentation Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first `/present` vertical slice that turns the prepared report workflow replay into a keyboard-driven, 720p-friendly React presentation stage.

**Architecture:** Keep the normal console as the product surface and add presentation mode as a separate React route. Presentation mode is a compositor over reusable scene components: a scripted beat controller drives chat, operation blocks, curated graph, node detail, trace/output, and evidence without building a generic layout engine.

**Tech Stack:** React 19, Vite, TypeScript, React Router, Motion for React, existing Valibot/demo timeline models, existing console tests with Vitest/Testing Library, Playwright smoke through `pnpx --package @playwright/test`.

## Global Constraints

- The first implementation is infrastructure with a provisional script, not the final defense talk.
- `/present` defaults to replay and must work without a workflow RPC server.
- Live workflow mutations must not be triggered by backward navigation.
- The normal console must remain product-like and not inherit cinematic layout choices.
- Presentation mode must be readable at `1280x720`.
- Use semantic beat state; do not store React components or large layer config objects in beat data.
- Keep TSX files lean by extracting focused scene components.
- Component extraction from existing console/demo UI is in scope when it prevents duplicate graph, timeline, operation evidence, output, or trace rendering.
- No slow typewriter effect; use instant messages with subtle fade/stagger.
- Every motion path needs a reduced-motion fallback.

---

## File Structure

Create the new presentation area under `web/apps/console/src/presentation/`:

```text
presentation/
  beats.ts                 # Beat ids, script metadata, hash helpers
  beats.test.ts
  presentation-state.ts    # Reducer and keyboard/hash-safe state transitions
  presentation-state.test.ts
  PresentationRoute.tsx    # Route shell and controller wiring
  PresentationRoute.test.tsx
  PresentationStage.tsx    # 720p stage compositor
  BeatRail.tsx
  StageCaption.tsx
  OperatorChat.tsx
  OperationBlock.tsx
  WorkflowGraphStage.tsx
  NodeSpotlight.tsx
  EvidenceDrawer.tsx
  presentation.css
```

Restructure the app route boundary:

```text
app/
  App.tsx                  # BrowserRouter only
  AppRoutes.tsx            # route table
  ConsoleHome.tsx          # current console body moved from App.tsx
```

Modify existing files:

```text
web/apps/console/package.json
web/apps/console/src/styles/global.css
web/apps/console/src/app/App.test.tsx
web/README.md
docs/current_roadmap.md
```

---

### Task 1: Route Split And Dependencies

**Files:**
- Modify: `web/apps/console/package.json`
- Create: `web/apps/console/src/app/AppRoutes.tsx`
- Create: `web/apps/console/src/app/ConsoleHome.tsx`
- Modify: `web/apps/console/src/app/App.tsx`
- Modify: `web/apps/console/src/app/App.test.tsx`
- Create: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Create: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Produces: `AppRoutes(): JSX.Element`
- Produces: `ConsoleHome(): JSX.Element`
- Produces: `PresentationRoute(): JSX.Element`
- Consumes: existing `LdaReportDemoPanel`, `useDemoTimeline`, `LifecycleExplorer`, `SourceInventory`

- [ ] **Step 1: Add dependencies**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console add react-router-dom motion
  ```

  Expected: `web/apps/console/package.json` and `web/pnpm-lock.yaml` update,
  and install exits 0. Do not hand-edit guessed package versions; let pnpm
  resolve the current compatible versions and commit the lockfile.

- [ ] **Step 2: Write failing route tests**

  Create `web/apps/console/src/presentation/PresentationRoute.test.tsx`:

  ```tsx
  import { cleanup, render, screen } from "@testing-library/react";
  import { afterEach, describe, expect, it } from "vitest";
  import { PresentationRoute } from "./PresentationRoute.js";

  afterEach(() => cleanup());

  describe("PresentationRoute", () => {
    it("renders the presentation stage entry point", () => {
      render(<PresentationRoute />);

      expect(screen.getByRole("main", { name: /lda.chat presentation/i })).toBeInTheDocument();
      expect(screen.getByText(/planner decisions/i)).toBeInTheDocument();
    });
  });
  ```

  Modify `web/apps/console/src/app/App.test.tsx` to add:

  ```tsx
  import { MemoryRouter } from "react-router-dom";
  import { AppRoutes } from "./AppRoutes.js";
  ```

  Add the test:

  ```tsx
  it("routes to presentation mode separately from the console", () => {
    render(
      <MemoryRouter initialEntries={["/present"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole("main", { name: /lda.chat presentation/i })).toBeInTheDocument();
    expect(screen.queryByLabelText("Lifecycle Explorer")).toBeNull();
  });
  ```

- [ ] **Step 3: Run tests and verify red**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx src/app/App.test.tsx
  ```

  Expected: FAIL because `PresentationRoute` and `AppRoutes` do not exist.

- [ ] **Step 4: Move current console body into `ConsoleHome`**

  Create `web/apps/console/src/app/ConsoleHome.tsx` by moving the current body of `App.tsx` into this component. Keep the current connection reducer, source loading, lifecycle explorer, and demo panel behavior unchanged.

  The exported component signature must be:

  ```tsx
  export const ConsoleHome = () => {
    // existing App implementation body, unchanged except component name
  };
  ```

- [ ] **Step 5: Replace `App.tsx` with router shell**

  Replace `web/apps/console/src/app/App.tsx` with:

  ```tsx
  import { BrowserRouter } from "react-router-dom";
  import { AppRoutes } from "./AppRoutes.js";

  export const App = () => (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
  ```

- [ ] **Step 6: Add route table and placeholder presentation route**

  Create `web/apps/console/src/app/AppRoutes.tsx`:

  ```tsx
  import { Navigate, Route, Routes } from "react-router-dom";
  import { ConsoleHome } from "./ConsoleHome.js";
  import { PresentationRoute } from "../presentation/PresentationRoute.js";

  export const AppRoutes = () => (
    <Routes>
      <Route path="/" element={<ConsoleHome />} />
      <Route path="/console" element={<ConsoleHome />} />
      <Route path="/present" element={<PresentationRoute />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
  ```

  Create `web/apps/console/src/presentation/PresentationRoute.tsx`:

  ```tsx
  export const PresentationRoute = () => (
    <main className="presentation-route" aria-label="lda.chat presentation">
      <p>Planner decisions are separated from deterministic runtime execution.</p>
    </main>
  );
  ```

- [ ] **Step 7: Run tests and verify green**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx src/app/App.test.tsx
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: PASS and typecheck clean.

- [ ] **Step 8: Commit**

  ```powershell
  git add web/apps/console/package.json web/pnpm-lock.yaml web/apps/console/src/app web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx
  git commit -m "feat: add presentation route shell"
  ```

---

### Task 2: Beat Model, Hash Navigation, And Keyboard Control

**Files:**
- Create: `web/apps/console/src/presentation/beats.ts`
- Create: `web/apps/console/src/presentation/beats.test.ts`
- Create: `web/apps/console/src/presentation/presentation-state.ts`
- Create: `web/apps/console/src/presentation/presentation-state.test.ts`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Produces: `type BeatId`
- Produces: `presentationBeats: readonly PresentationBeat[]`
- Produces: `beatFromHash(hash: string): BeatId`
- Produces: `hashForBeat(beat: BeatId): string`
- Produces: `presentationReducer(state, action): PresentationState`
- Produces: `usePresentationKeyboard(onNext, onPrevious, onClose): void` inside `PresentationRoute.tsx`

- [ ] **Step 1: Write beat helper tests**

  Create `web/apps/console/src/presentation/beats.test.ts`:

  ```ts
  import { describe, expect, it } from "vitest";
  import { beatFromHash, hashForBeat, presentationBeats } from "./beats.js";

  describe("presentation beats", () => {
    it("has stable unique beat ids", () => {
      const ids = presentationBeats.map((beat) => beat.id);
      expect(new Set(ids).size).toBe(ids.length);
      expect(ids).toEqual([
        "intro",
        "chat-request",
        "tool-call-start",
        "graph-reveal",
        "interrupt-approval",
        "resume-output",
        "trace-evidence",
        "boundary-wrap",
      ]);
    });

    it("maps beats to hash fragments and falls back to intro", () => {
      expect(hashForBeat("interrupt-approval")).toBe("#interrupt-approval");
      expect(beatFromHash("#interrupt-approval")).toBe("interrupt-approval");
      expect(beatFromHash("#missing")).toBe("intro");
      expect(beatFromHash("")).toBe("intro");
    });
  });
  ```

- [ ] **Step 2: Write reducer tests**

  Create `web/apps/console/src/presentation/presentation-state.test.ts`:

  ```ts
  import { describe, expect, it } from "vitest";
  import {
    initialPresentationState,
    presentationReducer,
  } from "./presentation-state.js";

  describe("presentationReducer", () => {
    it("advances and rewinds scripted beats without changing playback mode", () => {
      const advanced = presentationReducer(initialPresentationState, { type: "next" });
      const rewound = presentationReducer(advanced, { type: "previous" });

      expect(advanced.beat).toBe("chat-request");
      expect(advanced.playbackMode).toBe("replay");
      expect(rewound.beat).toBe("intro");
    });

    it("opens node detail without changing the current beat", () => {
      const state = presentationReducer(initialPresentationState, {
        type: "select_node",
        nodeId: "review_issues",
      });

      expect(state.beat).toBe("intro");
      expect(state.selectedNodeId).toBe("review_issues");
    });

    it("closes overlays before rewinding content", () => {
      const opened = presentationReducer(initialPresentationState, {
        type: "set_evidence_mode",
        mode: "open",
      });
      const closed = presentationReducer(opened, { type: "close_overlay" });

      expect(closed.evidenceMode).toBe("hidden");
      expect(closed.beat).toBe("intro");
    });
  });
  ```

- [ ] **Step 3: Run tests and verify red**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/presentation/beats.test.ts src/presentation/presentation-state.test.ts
  ```

  Expected: FAIL because modules do not exist.

- [ ] **Step 4: Implement beat model**

  Create `web/apps/console/src/presentation/beats.ts`:

  ```ts
  export type BeatId =
    | "intro"
    | "chat-request"
    | "tool-call-start"
    | "graph-reveal"
    | "interrupt-approval"
    | "resume-output"
    | "trace-evidence"
    | "boundary-wrap";

  export type PresentationBeat = {
    readonly id: BeatId;
    readonly title: string;
    readonly caption: string;
    readonly lifecycleStep: string;
  };

  export const presentationBeats: readonly PresentationBeat[] = [
    {
      id: "intro",
      title: "Planner vs runtime",
      caption: "External planners propose actions; the workflow runtime owns deterministic execution.",
      lifecycleStep: "Frame",
    },
    {
      id: "chat-request",
      title: "Operator request",
      caption: "The operator asks for a thesis readiness report through a chat-like product surface.",
      lifecycleStep: "Request",
    },
    {
      id: "tool-call-start",
      title: "Product operation",
      caption: "The assistant invokes a prepared workflow operation instead of inventing ad-hoc script state.",
      lifecycleStep: "Run",
    },
    {
      id: "graph-reveal",
      title: "Workflow graph",
      caption: "The graph shows reusable structure, not a one-off tool-calling transcript.",
      lifecycleStep: "Graph",
    },
    {
      id: "interrupt-approval",
      title: "Typed interrupt",
      caption: "Human approval is a typed workflow boundary with explicit resume outcomes.",
      lifecycleStep: "Interrupt",
    },
    {
      id: "resume-output",
      title: "Resume output",
      caption: "Resuming commits the approved branch and produces report and issue-board output.",
      lifecycleStep: "Resume",
    },
    {
      id: "trace-evidence",
      title: "Trace evidence",
      caption: "Run records and trace frames make the execution inspectable after the fact.",
      lifecycleStep: "Trace",
    },
    {
      id: "boundary-wrap",
      title: "Boundary",
      caption: "lda.chat is the workflow substrate that an external or scripted agent can operate.",
      lifecycleStep: "Boundary",
    },
  ] as const;

  const beatIds = new Set<BeatId>(presentationBeats.map((beat) => beat.id));

  export const beatFromHash = (hash: string): BeatId => {
    const id = hash.replace(/^#/, "") as BeatId;
    return beatIds.has(id) ? id : "intro";
  };

  export const hashForBeat = (beat: BeatId): string => `#${beat}`;
  ```

- [ ] **Step 5: Implement reducer**

  Create `web/apps/console/src/presentation/presentation-state.ts`:

  ```ts
  import { beatFromHash, presentationBeats, type BeatId } from "./beats.js";

  export type PresentationState = {
    readonly beat: BeatId;
    readonly selectedNodeId: string | null;
    readonly chatMode: "full" | "rail" | "hidden";
    readonly evidenceMode: "hidden" | "peek" | "open";
    readonly playbackMode: "replay" | "live";
  };

  export type PresentationAction =
    | { readonly type: "next" }
    | { readonly type: "previous" }
    | { readonly type: "jump"; readonly beat: BeatId }
    | { readonly type: "jump_hash"; readonly hash: string }
    | { readonly type: "select_node"; readonly nodeId: string }
    | { readonly type: "clear_node" }
    | { readonly type: "set_evidence_mode"; readonly mode: PresentationState["evidenceMode"] }
    | { readonly type: "close_overlay" }
    | { readonly type: "set_playback_mode"; readonly mode: PresentationState["playbackMode"] };

  export const initialPresentationState: PresentationState = {
    beat: "intro",
    selectedNodeId: null,
    chatMode: "full",
    evidenceMode: "hidden",
    playbackMode: "replay",
  };

  const beatIndex = (beat: BeatId): number =>
    presentationBeats.findIndex((candidate) => candidate.id === beat);

  const withDerivedModes = (state: PresentationState, beat: BeatId): PresentationState => ({
    ...state,
    beat,
    chatMode: beat === "intro" || beat === "chat-request" ? "full" : "rail",
    evidenceMode: beat === "trace-evidence" ? "peek" : state.evidenceMode,
  });

  export const presentationReducer = (
    state: PresentationState,
    action: PresentationAction,
  ): PresentationState => {
    switch (action.type) {
      case "next": {
        const next = Math.min(beatIndex(state.beat) + 1, presentationBeats.length - 1);
        return withDerivedModes(state, presentationBeats[next]?.id ?? state.beat);
      }
      case "previous": {
        const previous = Math.max(beatIndex(state.beat) - 1, 0);
        return withDerivedModes(state, presentationBeats[previous]?.id ?? state.beat);
      }
      case "jump":
        return withDerivedModes(state, action.beat);
      case "jump_hash":
        return withDerivedModes(state, beatFromHash(action.hash));
      case "select_node":
        return { ...state, selectedNodeId: action.nodeId };
      case "clear_node":
        return { ...state, selectedNodeId: null };
      case "set_evidence_mode":
        return { ...state, evidenceMode: action.mode };
      case "close_overlay":
        if (state.evidenceMode !== "hidden") return { ...state, evidenceMode: "hidden" };
        if (state.selectedNodeId !== null) return { ...state, selectedNodeId: null };
        return state;
      case "set_playback_mode":
        return { ...state, playbackMode: action.mode };
    }
  };
  ```

- [ ] **Step 6: Wire hash and keyboard in route**

  Modify `web/apps/console/src/presentation/PresentationRoute.tsx` to use the reducer:

  ```tsx
  import { useEffect, useReducer } from "react";
  import { hashForBeat, presentationBeats } from "./beats.js";
  import {
    initialPresentationState,
    presentationReducer,
  } from "./presentation-state.js";

  export const PresentationRoute = () => {
    const [state, dispatch] = useReducer(
      presentationReducer,
      initialPresentationState,
      (initial) => presentationReducer(initial, { type: "jump_hash", hash: window.location.hash }),
    );

    useEffect(() => {
      const hash = hashForBeat(state.beat);
      if (window.location.hash !== hash) {
        window.history.replaceState(null, "", hash);
      }
    }, [state.beat]);

    useEffect(() => {
      const onKeyDown = (event: KeyboardEvent) => {
        if (event.key === " " || event.key === "ArrowRight") {
          event.preventDefault();
          dispatch({ type: "next" });
        } else if (event.key === "ArrowLeft") {
          event.preventDefault();
          dispatch({ type: "previous" });
        } else if (event.key === "Escape") {
          dispatch({ type: "close_overlay" });
        }
      };
      window.addEventListener("keydown", onKeyDown);
      return () => window.removeEventListener("keydown", onKeyDown);
    }, []);

    const beat = presentationBeats.find((candidate) => candidate.id === state.beat) ?? presentationBeats[0];

    return (
      <main className="presentation-route" aria-label="lda.chat presentation">
        <p>{beat.caption}</p>
      </main>
    );
  };
  ```

- [ ] **Step 7: Extend route tests for keyboard and hash**

  In `PresentationRoute.test.tsx`, add:

  ```tsx
  it("starts from a hash beat and advances with keyboard", async () => {
    window.location.hash = "#interrupt-approval";
    render(<PresentationRoute />);

    expect(screen.getByText(/Human approval is a typed workflow boundary/i)).toBeInTheDocument();

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    expect(await screen.findByText(/Resuming commits the approved branch/i)).toBeInTheDocument();
  });
  ```

- [ ] **Step 8: Run tests and verify green**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/presentation
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: PASS and typecheck clean.

- [ ] **Step 9: Commit**

  ```powershell
  git add web/apps/console/src/presentation
  git commit -m "feat: add presentation beat controller"
  ```

---

### Task 3: Replay-Backed Stage And Scene Components

**Files:**
- Create: `web/apps/console/src/presentation/PresentationStage.tsx`
- Create: `web/apps/console/src/presentation/BeatRail.tsx`
- Create: `web/apps/console/src/presentation/StageCaption.tsx`
- Create: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Consumes: `PresentationState`, `presentationBeats`
- Consumes: `useDemoTimeline(null, recordEvidence)` for replay data
- Produces: `PresentationStage(props): JSX.Element`
- Produces: `BeatRail(props): JSX.Element`
- Produces: `OperatorChat(props): JSX.Element`

- [ ] **Step 1: Write failing stage test**

  Add to `PresentationRoute.test.tsx`:

  ```tsx
  it("renders replay-first chat, beat rail, and stage caption", () => {
    render(<PresentationRoute />);

    expect(screen.getByText(/Operator/i)).toBeInTheDocument();
    expect(screen.getByText(/Prepare the thesis readiness report/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/presentation beat rail/i)).toBeInTheDocument();
    expect(screen.getByText(/Replay/i)).toBeInTheDocument();
  });
  ```

- [ ] **Step 2: Run test and verify red**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
  ```

  Expected: FAIL because scene components are missing.

- [ ] **Step 3: Implement `StageCaption`**

  Create `web/apps/console/src/presentation/StageCaption.tsx`:

  ```tsx
  import type { ReactNode } from "react";

  type StageCaptionProps = {
    readonly eyebrow: string;
    readonly title: string;
    readonly children: ReactNode;
  };

  export const StageCaption = ({ eyebrow, title, children }: StageCaptionProps) => (
    <section className="stage-caption" aria-label={title}>
      <p className="stage-caption__eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <div>{children}</div>
    </section>
  );
  ```

  `children` is `ReactNode` so future beats can include short tables, charts, or `<a>`/`<Link>` elements without changing the caption API.

- [ ] **Step 4: Implement `BeatRail`**

  Create `web/apps/console/src/presentation/BeatRail.tsx`:

  ```tsx
  import { presentationBeats, type BeatId } from "./beats.js";

  type BeatRailProps = {
    readonly activeBeat: BeatId;
    readonly jump: (beat: BeatId) => void;
  };

  export const BeatRail = ({ activeBeat, jump }: BeatRailProps) => (
    <nav className="beat-rail" aria-label="presentation beat rail">
      {presentationBeats.map((beat) => (
        <button
          key={beat.id}
          type="button"
          data-active={beat.id === activeBeat}
          onClick={() => jump(beat.id)}
        >
          <span>{beat.lifecycleStep}</span>
          <small>{beat.title}</small>
        </button>
      ))}
    </nav>
  );
  ```

- [ ] **Step 5: Implement `OperatorChat`**

  Create `web/apps/console/src/presentation/OperatorChat.tsx`:

  ```tsx
  import type { PresentationState } from "./presentation-state.js";

  type OperatorChatProps = {
    readonly state: PresentationState;
  };

  export const OperatorChat = ({ state }: OperatorChatProps) => (
    <aside className="operator-chat" data-mode={state.chatMode} aria-label="scripted operator chat">
      <div className="chat-message chat-message--operator">
        <strong>Operator</strong>
        <p>Prepare the thesis readiness report.</p>
      </div>
      <div className="chat-message chat-message--system">
        <strong>lda.chat</strong>
        <p>Found prepared workflow recipe: <code>lda_report_case_study</code>.</p>
      </div>
      <div className="chat-message chat-message--system">
        <strong>lda.chat</strong>
        <p>Replay mode is active. Live execution is available when connected.</p>
      </div>
    </aside>
  );
  ```

- [ ] **Step 6: Implement `PresentationStage`**

  Create `web/apps/console/src/presentation/PresentationStage.tsx`:

  ```tsx
  import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
  import { presentationBeats, type BeatId } from "./beats.js";
  import { BeatRail } from "./BeatRail.js";
  import { OperatorChat } from "./OperatorChat.js";
  import { StageCaption } from "./StageCaption.js";
  import type { PresentationState } from "./presentation-state.js";

  type PresentationStageProps = {
    readonly state: PresentationState;
    readonly demo: DemoTimelineController;
    readonly jump: (beat: BeatId) => void;
  };

  export const PresentationStage = ({ state, demo, jump }: PresentationStageProps) => {
    const beat = presentationBeats.find((candidate) => candidate.id === state.beat) ?? presentationBeats[0];

    return (
      <div className="presentation-stage" data-beat={state.beat}>
        <OperatorChat state={state} />
        <section className="presentation-stage__main">
          <StageCaption eyebrow="lda.chat defense" title={beat.title}>
            <p>{beat.caption}</p>
          </StageCaption>
          <p className="presentation-stage__mode">
            {demo.state.mode === "replay" ? "Replay" : "Live"} · {demo.state.phase}
          </p>
        </section>
        <BeatRail activeBeat={state.beat} jump={jump} />
      </div>
    );
  };
  ```

- [ ] **Step 7: Wire stage into route**

  In `PresentationRoute.tsx`, import `useDemoTimeline`, `PresentationStage`, and local evidence recorder:

  ```tsx
  import { useCallback, useEffect, useReducer, useState } from "react";
  import type { EvidenceRecord } from "../app/state.js";
  import { useDemoTimeline } from "../demo/useDemoTimeline.js";
  import { PresentationStage } from "./PresentationStage.js";
  ```

  Add:

  ```tsx
  const [evidence, setEvidence] = useState<readonly EvidenceRecord[]>([]);
  const recordEvidence = useCallback((record: EvidenceRecord) => {
    setEvidence((records) => [...records, record]);
  }, []);
  const demo = useDemoTimeline(null, recordEvidence);
  ```

  Replace the `<p>{beat.caption}</p>` route body with:

  ```tsx
  <PresentationStage
    state={state}
    demo={demo}
    jump={(beatId) => dispatch({ type: "jump", beat: beatId })}
  />
  ```

  Keep `evidence` in state even if unused in this task so Task 6 can render it without changing the controller boundary. To avoid an unused variable, pass it later only after Task 6; for this task, name it `_evidence`:

  ```tsx
  const [_evidence, setEvidence] = useState<readonly EvidenceRecord[]>([]);
  ```

- [ ] **Step 8: Add CSS entrypoint**

  Create `web/apps/console/src/presentation/presentation.css`:

  ```css
  .presentation-route {
    min-height: 100vh;
    background: oklch(0.12 0.025 250);
    color: oklch(0.96 0.01 250);
  }

  .presentation-stage {
    min-height: 100vh;
    display: grid;
    grid-template-rows: 1fr auto;
    gap: 1rem;
    padding: 1.25rem;
  }

  .presentation-stage__main {
    display: grid;
    align-content: center;
    gap: 1rem;
    max-width: 72rem;
  }

  .operator-chat {
    max-width: 48rem;
    display: grid;
    gap: 0.75rem;
  }

  .operator-chat[data-mode="rail"] {
    max-width: 22rem;
  }

  .chat-message {
    border: 1px solid oklch(0.34 0.035 250);
    background: oklch(0.18 0.025 250);
    padding: 0.85rem 1rem;
    border-radius: 0.85rem;
  }

  .beat-rail {
    display: flex;
    gap: 0.5rem;
    overflow-x: auto;
  }

  .beat-rail button {
    min-width: 8rem;
    text-align: left;
    border: 1px solid oklch(0.36 0.04 250);
    background: oklch(0.18 0.025 250);
    color: inherit;
    padding: 0.65rem 0.75rem;
  }

  .beat-rail button[data-active="true"] {
    background: oklch(0.7 0.16 195);
    color: oklch(0.12 0.025 250);
  }
  ```

  Import it in `PresentationRoute.tsx`:

  ```tsx
  import "./presentation.css";
  ```

- [ ] **Step 9: Run tests and verify green**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/presentation/PresentationRoute.test.tsx
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: PASS and typecheck clean.

- [ ] **Step 10: Commit**

  ```powershell
  git add web/apps/console/src/presentation
  git commit -m "feat: render presentation stage shell"
  ```

---

### Task 4: Operation Block And Replay Event Interpretation

**Files:**
- Create: `web/apps/console/src/presentation/OperationBlock.tsx`
- Create: `web/apps/console/src/presentation/OperationBlock.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: `DemoEvent` from `../demo/timeline/models.js`
- Produces: `OperationBlock({ event }): JSX.Element`

- [ ] **Step 1: Write failing operation block tests**

  Create `web/apps/console/src/presentation/OperationBlock.test.tsx`:

  ```tsx
  import { cleanup, render, screen } from "@testing-library/react";
  import { afterEach, describe, expect, it } from "vitest";
  import type { DemoEvent } from "../demo/timeline/models.js";
  import { OperationBlock } from "./OperationBlock.js";

  afterEach(() => cleanup());

  const event: DemoEvent = {
    id: "recorded-1-run-start",
    sequence: 1,
    stage: "run_start",
    operation: "workflow.runs.start",
    reason: "Start the prepared report workflow.",
    equivalentCli: "uv run wf run start lda_report_case_study.default --input '<json>'",
    params: { deployment_id: "lda_report_case_study.default" },
    rawResponse: { result: { status: "interrupted" } },
    interpreted: {
      status: "interrupted",
      interrupt: { kind: "issue_review" },
    },
    durationMs: 88,
    resultingIds: {
      deploymentId: "lda_report_case_study.default",
      runId: "run_demo",
    },
    recordedAt: "2026-07-03T00:00:01.000Z",
  };

  describe("OperationBlock", () => {
    it("shows command, raw response, and interpreted result", () => {
      render(<OperationBlock event={event} />);

      expect(screen.getByText(/workflow.runs.start/i)).toBeInTheDocument();
      expect(screen.getByText(/uv run wf run start/i)).toBeInTheDocument();
      expect(screen.getByText(/status/i)).toBeInTheDocument();
      expect(screen.getByText(/issue_review/i)).toBeInTheDocument();
      expect(screen.getByText(/run_demo/i)).toBeInTheDocument();
    });
  });
  ```

- [ ] **Step 2: Run test and verify red**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/presentation/OperationBlock.test.tsx
  ```

  Expected: FAIL because `OperationBlock` does not exist.

- [ ] **Step 3: Implement `OperationBlock`**

  Create `web/apps/console/src/presentation/OperationBlock.tsx`:

  ```tsx
  import type { DemoEvent } from "../demo/timeline/models.js";

  const formatJson = (value: unknown): string => JSON.stringify(value, null, 2);

  type OperationBlockProps = {
    readonly event: DemoEvent;
  };

  export const OperationBlock = ({ event }: OperationBlockProps) => (
    <section className="operation-block" aria-label={`${event.stage} operation`}>
      <header>
        <p>{event.operation ?? event.stage}</p>
        <small>{event.durationMs} ms</small>
      </header>
      {event.equivalentCli && (
        <pre className="operation-block__command"><code>{event.equivalentCli}</code></pre>
      )}
      <div className="operation-block__grid">
        <section>
          <h3>Raw</h3>
          <pre><code>{formatJson(event.rawResponse)}</code></pre>
        </section>
        <section>
          <h3>Interpreted</h3>
          <pre><code>{formatJson(event.interpreted)}</code></pre>
        </section>
      </div>
      <footer>
        <span>{event.resultingIds.deploymentId}</span>
        {event.resultingIds.runId && <span>{event.resultingIds.runId}</span>}
      </footer>
    </section>
  );
  ```

- [ ] **Step 4: Select event for current beat**

  In `PresentationStage.tsx`, derive a visible operation event from the demo timeline:

  ```tsx
  const operationEvent =
    demo.state.events.find((event) => event.stage === "run_start") ??
    demo.state.events.find((event) => event.operation !== null) ??
    null;
  ```

  Render it after `StageCaption` when present:

  ```tsx
  {operationEvent && <OperationBlock event={operationEvent} />}
  ```

  Import:

  ```tsx
  import { OperationBlock } from "./OperationBlock.js";
  ```

- [ ] **Step 5: Update route test to prove operation block can appear**

  Add to `PresentationRoute.test.tsx`:

  ```tsx
  it("can advance replay far enough to show a product operation block", async () => {
    render(<PresentationRoute />);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));

    expect(await screen.findByText(/workflow.runs.start/i)).toBeInTheDocument();
  });
  ```

  If the replay controller does not auto-start yet, this test will fail until Task 5 starts replay on mount. Keep the test here to pin the intended behavior.

- [ ] **Step 6: Add operation CSS**

  Append to `presentation.css`:

  ```css
  .operation-block {
    border: 1px solid oklch(0.36 0.04 250);
    background: oklch(0.16 0.025 250);
    padding: 1rem;
    border-radius: 0.85rem;
  }

  .operation-block header,
  .operation-block footer {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    color: oklch(0.78 0.035 250);
  }

  .operation-block__command,
  .operation-block pre {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .operation-block__grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }

  @media (max-width: 800px) {
    .operation-block__grid {
      grid-template-columns: 1fr;
    }
  }
  ```

- [ ] **Step 7: Run tests and verify green or document dependency on Task 5**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/presentation/OperationBlock.test.tsx src/presentation/PresentationRoute.test.tsx
  ```

  Expected: `OperationBlock.test.tsx` PASS. If `PresentationRoute.test.tsx` fails because replay is not started on mount, leave the test failing and complete Task 5 immediately.

- [ ] **Step 8: Commit if all tests green; otherwise defer commit until Task 5**

  If green:

  ```powershell
  git add web/apps/console/src/presentation
  git commit -m "feat: show presentation operation blocks"
  ```

---

### Task 5: Replay Startup, Graph Stage, And Node Spotlight

**Files:**
- Create: `web/apps/console/src/presentation/WorkflowGraphStage.tsx`
- Create: `web/apps/console/src/presentation/NodeSpotlight.tsx`
- Create: `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Produces: `presentationNodes`
- Produces: `WorkflowGraphStage({ selectedNodeId, selectNode })`
- Produces: `NodeSpotlight({ nodeId, close })`

- [ ] **Step 1: Write graph/spotlight tests**

  Create `web/apps/console/src/presentation/WorkflowGraphStage.test.tsx`:

  ```tsx
  import { cleanup, render, screen } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { afterEach, describe, expect, it, vi } from "vitest";
  import { WorkflowGraphStage } from "./WorkflowGraphStage.js";

  afterEach(() => cleanup());

  describe("WorkflowGraphStage", () => {
    it("renders curated workflow nodes and allows node selection", async () => {
      const selectNode = vi.fn();
      render(<WorkflowGraphStage selectedNodeId={null} selectNode={selectNode} />);

      await userEvent.click(screen.getByRole("button", { name: /issue review/i }));
      expect(selectNode).toHaveBeenCalledWith("review_issues");
    });
  });
  ```

  Add to `PresentationRoute.test.tsx`:

  ```tsx
  it("shows node spotlight when a graph node is selected", async () => {
    render(<PresentationRoute />);
    await userEvent.click(screen.getByRole("button", { name: /issue review/i }));

    expect(screen.getByRole("dialog", { name: /issue review/i })).toBeInTheDocument();
    expect(screen.getByText(/NodeUse/i)).toBeInTheDocument();
  });
  ```

  Add missing import:

  ```tsx
  import userEvent from "@testing-library/user-event";
  ```

- [ ] **Step 2: Run tests and verify red**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/presentation/WorkflowGraphStage.test.tsx src/presentation/PresentationRoute.test.tsx
  ```

  Expected: FAIL because graph components do not exist.

- [ ] **Step 3: Implement curated graph**

  Create `web/apps/console/src/presentation/WorkflowGraphStage.tsx`:

  ```tsx
  export type PresentationNode = {
    readonly id: string;
    readonly label: string;
    readonly kind: "node" | "interrupt" | "end";
    readonly x: number;
    readonly y: number;
  };

  export const presentationNodes: readonly PresentationNode[] = [
    { id: "read_docs", label: "Read docs", kind: "node", x: 8, y: 45 },
    { id: "build_report", label: "Build report", kind: "node", x: 30, y: 30 },
    { id: "review_issues", label: "Issue review", kind: "interrupt", x: 52, y: 45 },
    { id: "create_issues", label: "Create issues", kind: "node", x: 74, y: 30 },
    { id: "end_completed", label: "Completed", kind: "end", x: 92, y: 45 },
  ];

  type WorkflowGraphStageProps = {
    readonly selectedNodeId: string | null;
    readonly selectNode: (nodeId: string) => void;
  };

  export const WorkflowGraphStage = ({ selectedNodeId, selectNode }: WorkflowGraphStageProps) => (
    <section className="workflow-graph-stage" aria-label="workflow graph">
      {presentationNodes.map((node) => (
        <button
          key={node.id}
          type="button"
          className="workflow-graph-stage__node"
          data-kind={node.kind}
          data-selected={selectedNodeId === node.id}
          style={{ left: `${node.x}%`, top: `${node.y}%` }}
          onClick={() => selectNode(node.id)}
        >
          {node.label}
        </button>
      ))}
    </section>
  );
  ```

- [ ] **Step 4: Implement node spotlight**

  Create `web/apps/console/src/presentation/NodeSpotlight.tsx`:

  ```tsx
  import { presentationNodes } from "./WorkflowGraphStage.js";

  type NodeSpotlightProps = {
    readonly nodeId: string;
    readonly close: () => void;
  };

  const nodeDescription = (nodeId: string): string => {
    if (nodeId === "review_issues") {
      return "NodeUse of a typed interrupt boundary. It exposes request and resume schemas and waits for a submitted or cancelled outcome.";
    }
    if (nodeId === "create_issues") {
      return "NodeUse that writes selected review items into the local issue-board source.";
    }
    return "NodeUse in the prepared report workflow. The presentation graph is curated, but every node maps back to real workflow/run evidence.";
  };

  export const NodeSpotlight = ({ nodeId, close }: NodeSpotlightProps) => {
    const node = presentationNodes.find((candidate) => candidate.id === nodeId);
    if (!node) return null;

    return (
      <aside className="node-spotlight" role="dialog" aria-label={node.label}>
        <button type="button" onClick={close}>Close</button>
        <p>NodeUse</p>
        <h2>{node.label}</h2>
        <p>{nodeDescription(node.id)}</p>
      </aside>
    );
  };
  ```

- [ ] **Step 5: Wire graph and spotlight into stage**

  In `PresentationStage.tsx`, import:

  ```tsx
  import { WorkflowGraphStage } from "./WorkflowGraphStage.js";
  import { NodeSpotlight } from "./NodeSpotlight.js";
  ```

  Add props:

  ```ts
  readonly selectNode: (nodeId: string) => void;
  readonly clearNode: () => void;
  ```

  Render graph inside `presentation-stage__main`:

  ```tsx
  <WorkflowGraphStage selectedNodeId={state.selectedNodeId} selectNode={selectNode} />
  {state.selectedNodeId && (
    <NodeSpotlight nodeId={state.selectedNodeId} close={clearNode} />
  )}
  ```

  In `PresentationRoute.tsx`, pass:

  ```tsx
  selectNode={(nodeId) => dispatch({ type: "select_node", nodeId })}
  clearNode={() => dispatch({ type: "clear_node" })}
  ```

- [ ] **Step 6: Start replay automatically on presentation route mount**

  In `PresentationRoute.tsx`, add:

  ```tsx
  useEffect(() => {
    if (demo.state.phase === "ready") {
      demo.setMode("replay");
      demo.start();
    }
  }, [demo]);
  ```

  If this causes an effect loop because `demo` is not stable, narrow the dependency to:

  ```tsx
  useEffect(() => {
    if (demo.state.phase === "ready") {
      demo.setMode("replay");
      demo.start();
    }
  }, [demo.state.phase, demo.setMode, demo.start]);
  ```

- [ ] **Step 7: Add graph CSS**

  Append to `presentation.css`:

  ```css
  .workflow-graph-stage {
    position: relative;
    min-height: 16rem;
    border: 1px solid oklch(0.32 0.04 250);
    background: oklch(0.14 0.025 250);
    overflow: hidden;
  }

  .workflow-graph-stage__node {
    position: absolute;
    transform: translate(-50%, -50%);
    border: 1px solid oklch(0.44 0.055 250);
    background: oklch(0.2 0.03 250);
    color: inherit;
    padding: 0.7rem 0.9rem;
    border-radius: 0.8rem;
  }

  .workflow-graph-stage__node[data-kind="interrupt"] {
    border-color: oklch(0.76 0.18 70);
  }

  .workflow-graph-stage__node[data-selected="true"] {
    outline: 3px solid oklch(0.72 0.17 195);
  }

  .node-spotlight {
    position: fixed;
    right: 1.25rem;
    top: 1.25rem;
    width: min(28rem, calc(100vw - 2.5rem));
    border: 1px solid oklch(0.42 0.05 250);
    background: oklch(0.17 0.025 250);
    color: inherit;
    padding: 1rem;
    z-index: 20;
  }
  ```

- [ ] **Step 8: Run tests and verify green**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/presentation
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: PASS and typecheck clean.

- [ ] **Step 9: Commit**

  ```powershell
  git add web/apps/console/src/presentation
  git commit -m "feat: add presentation graph spotlight"
  ```

---

### Task 6: Evidence Drawer, 720p Browser Smoke, And Docs

**Files:**
- Create: `web/apps/console/src/presentation/EvidenceDrawer.tsx`
- Create: `web/apps/console/src/presentation/EvidenceDrawer.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`

**Interfaces:**
- Consumes: local `EvidenceRecord[]` from `PresentationRoute`
- Produces: `EvidenceDrawer({ records, mode, close }): JSX.Element`

- [ ] **Step 1: Write failing evidence drawer test**

  Create `web/apps/console/src/presentation/EvidenceDrawer.test.tsx`:

  ```tsx
  import { cleanup, render, screen } from "@testing-library/react";
  import { afterEach, describe, expect, it, vi } from "vitest";
  import type { EvidenceRecord } from "../app/state.js";
  import { EvidenceDrawer } from "./EvidenceDrawer.js";

  afterEach(() => cleanup());

  const record: EvidenceRecord = {
    id: "demo-run-start",
    operation: "workflow.runs.start",
    label: "Start run",
    equivalentCli: "uv run wf run start lda_report_case_study.default",
    request: { deployment_id: "lda_report_case_study.default" },
    response: { result: { status: "interrupted" } },
    durationMs: 88,
  };

  describe("EvidenceDrawer", () => {
    it("renders current evidence records and can close", () => {
      const close = vi.fn();
      render(<EvidenceDrawer records={[record]} mode="open" close={close} />);

      expect(screen.getByRole("complementary", { name: /presentation evidence/i })).toBeInTheDocument();
      expect(screen.getByText(/workflow.runs.start/i)).toBeInTheDocument();
      expect(screen.getByText(/status/i)).toBeInTheDocument();
    });
  });
  ```

- [ ] **Step 2: Run test and verify red**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- src/presentation/EvidenceDrawer.test.tsx
  ```

  Expected: FAIL because `EvidenceDrawer` does not exist.

- [ ] **Step 3: Implement `EvidenceDrawer`**

  Create `web/apps/console/src/presentation/EvidenceDrawer.tsx`:

  ```tsx
  import type { EvidenceRecord } from "../app/state.js";
  import type { PresentationState } from "./presentation-state.js";

  const formatJson = (value: unknown): string => JSON.stringify(value, null, 2);

  type EvidenceDrawerProps = {
    readonly records: readonly EvidenceRecord[];
    readonly mode: PresentationState["evidenceMode"];
    readonly close: () => void;
  };

  export const EvidenceDrawer = ({ records, mode, close }: EvidenceDrawerProps) => {
    if (mode === "hidden") return null;

    return (
      <aside className="evidence-drawer" data-mode={mode} aria-label="presentation evidence">
        <header>
          <h2>Evidence</h2>
          <button type="button" onClick={close}>Close</button>
        </header>
        {records.length === 0 ? (
          <p>No live evidence captured in this view yet. Replay operation blocks still show recorded evidence.</p>
        ) : (
          records.map((record) => (
            <article key={record.id}>
              <h3>{record.operation}</h3>
              <p>{record.label}</p>
              <pre><code>{record.equivalentCli}</code></pre>
              <pre><code>{formatJson(record.response)}</code></pre>
            </article>
          ))
        )}
      </aside>
    );
  };
  ```

- [ ] **Step 4: Wire evidence into route/stage**

  Rename `_evidence` in `PresentationRoute.tsx` to `evidence`.

  Add `openEvidence` and `closeOverlay` props to `PresentationStage`:

  ```ts
  readonly evidence: readonly EvidenceRecord[];
  readonly openEvidence: () => void;
  readonly closeOverlay: () => void;
  ```

  Pass from route:

  ```tsx
  evidence={evidence}
  openEvidence={() => dispatch({ type: "set_evidence_mode", mode: "open" })}
  closeOverlay={() => dispatch({ type: "close_overlay" })}
  ```

  In `PresentationStage.tsx`, import and render:

  ```tsx
  import { EvidenceDrawer } from "./EvidenceDrawer.js";
  ```

  Add a button near the stage header:

  ```tsx
  <button type="button" onClick={openEvidence}>Evidence</button>
  ```

  Render drawer:

  ```tsx
  <EvidenceDrawer records={evidence} mode={state.evidenceMode} close={closeOverlay} />
  ```

- [ ] **Step 5: Add evidence CSS and 720p guardrails**

  Append:

  ```css
  .evidence-drawer {
    position: fixed;
    inset: 0 0 0 auto;
    width: min(36rem, 90vw);
    padding: 1rem;
    overflow: auto;
    background: oklch(0.13 0.025 250);
    border-left: 1px solid oklch(0.34 0.04 250);
    z-index: 30;
  }

  .evidence-drawer pre {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  @media (max-height: 760px) {
    .presentation-stage {
      padding: 0.75rem;
      gap: 0.65rem;
    }

    .stage-caption h1 {
      font-size: clamp(1.8rem, 4vw, 3rem);
    }

    .workflow-graph-stage {
      min-height: 12rem;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .presentation-route *,
    .presentation-route *::before,
    .presentation-route *::after {
      animation-duration: 0.01ms !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
  ```

- [ ] **Step 6: Update docs**

  In `web/README.md`, add a short section:

  ```md
  ### Presentation Mode

  The console also exposes `/present`, a replay-first defense route for the
  prepared `lda_report_workflow` story. It uses the same demo timeline data as
  the console demo, but renders a 720p-friendly staged view with keyboard beat
  navigation, operation blocks, graph node spotlight, and evidence drawer.

  ```powershell
  pnpm --dir web dev
  # open http://127.0.0.1:5173/present
  ```
  ```

  In `docs/current_roadmap.md`, mark the presentation route foundation as completed only after the browser smoke passes:

  ```md
  7. Completed: React presentation mode foundation for the prepared workflow demo...
  ```

- [ ] **Step 7: Run full web verification**

  Run:

  ```powershell
  pnpm --dir web test
  pnpm --dir web typecheck
  pnpm --dir web build
  ```

  Expected:

  - console, RPC, and server tests pass
  - typecheck clean
  - build clean

- [ ] **Step 8: Run Playwright smoke**

  Create a temporary spec at `tmp-playwright/presentation-smoke.spec.ts`:

  ```ts
  import { expect, test } from "@playwright/test";

  test("presentation route is keyboard navigable at 720p", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto("http://127.0.0.1:5173/present");

    await expect(page.getByRole("main", { name: /lda.chat presentation/i })).toBeVisible();
    await expect(page.getByText(/Replay/i)).toBeVisible();

    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    await expect(page.getByText(/workflow.runs.start/i)).toBeVisible();

    await page.getByRole("button", { name: /issue review/i }).click();
    await expect(page.getByRole("dialog", { name: /issue review/i })).toBeVisible();

    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: /^Evidence$/ }).click();
    await expect(page.getByRole("complementary", { name: /presentation evidence/i })).toBeVisible();
  });
  ```

  With `pnpm --dir web dev` already running, run:

  ```powershell
  pnpx --package @playwright/test playwright test tmp-playwright/presentation-smoke.spec.ts --browser=chromium --reporter=line
  ```

  Expected: PASS.

  Remove the temporary spec and generated screenshots/test-results after the smoke:

  ```powershell
  Remove-Item -LiteralPath tmp-playwright\presentation-smoke.spec.ts -ErrorAction SilentlyContinue
  Remove-Item -Recurse -Force test-results -ErrorAction SilentlyContinue
  ```

- [ ] **Step 9: Commit**

  ```powershell
  git add web/apps/console/src/presentation web/README.md docs/current_roadmap.md
  git commit -m "feat: add presentation evidence stage"
  ```

---

## Final Review Checklist

- [ ] Search the plan, spec, and presentation source for placeholder markers and
      stale Astro-first wording before final commit.
- [ ] `pnpm --dir web test` passes.
- [ ] `pnpm --dir web typecheck` passes.
- [ ] `pnpm --dir web build` passes.
- [ ] Playwright smoke passes at `1280x720`.
- [ ] `/` and `/console` still show the normal console.
- [ ] `/present` defaults to replay and can be driven by keyboard.
- [ ] `#interrupt-approval` deep link lands on the interrupt beat.
- [ ] Clicking a graph node opens `NodeSpotlight`; `Esc` closes it.
- [ ] Back navigation rewinds beat state and does not trigger workflow mutation calls.

## Self-Review Notes

Spec coverage:

- Route, replay default, hash navigation, keyboard controls: Tasks 1-2.
- Provisional script and beat editing: Task 2.
- Component extraction and lean TSX files: Tasks 1, 3, 5, 6.
- Operation block: Task 4.
- Curated graph and NodeUse detail: Task 5.
- Evidence drawer and 720p smoke: Task 6.
- Console remains product-like: Task 1 route split and final checklist.

Known deferred work:

- Final defense copy and polished visual identity.
- Real constrained demo agent macro.
- Static slide/appendix shell.
- Advanced motion choreography beyond basic CSS and Motion dependency setup.

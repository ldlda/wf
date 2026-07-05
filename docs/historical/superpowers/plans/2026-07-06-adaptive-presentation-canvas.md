# Adaptive Presentation Canvas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/present` use the available stage continuously from `4:3` through `16:9`, and replace the resizing right evidence drawer with a bottom-row receipt and explicit centered inspector.

**Architecture:** Keep a fixed logical height of `720px`, derive a clamped logical width from the viewport, and scale the resulting canvas as one unit. Use CSS container queries for compact composition. Migrate evidence from geometric `peek/open` modes to semantic `hidden/receipt/inspector` states, project existing `EvidenceRecord` data through focused receipt and inspector components, and remove the old drawer without a compatibility path.

**Tech Stack:** React 19, TypeScript 6, Vitest, Testing Library, CSS container queries, Motion's existing reduced-motion boundary, and Playwright browser automation for real layout checks.

## Global Constraints

- Follow the approved [adaptive presentation canvas and evidence inspector design](../specs/2026-07-05-adaptive-presentation-canvas-design.md).
- Preserve one logical height of exactly `720px`.
- Clamp logical width to exactly `960px` through `1280px`, covering `4:3` through `16:9`.
- Do not add a URL, query-string, local-storage, or hidden aspect-ratio override.
- Aspect ratio may change placement and wrapping, but not claims, graph nodes, controls, labels, or evidence records.
- Evidence availability must never resize the primary presentation region.
- Beat metadata may request only `hidden` or `receipt`; opening `inspector` is always an explicit action.
- Compact chat and evidence must not overlap; the inspector takes precedence while open.
- Preserve scene, beat, Figure Focus Path, replay, and canonical evidence data contracts.
- Do not change scene-specific graph layout, Dagre spacing, Figure Node positions, captions, or overflow tuning in this slice. Those visuals are a separate slice.
- Do not add a second evidence store, transport, responsive framework, dialog dependency, or compatibility wrapper for `EvidenceDrawer`.
- Keep comments around non-obvious viewport math, focus restoration, and container-query ownership.
- Use test-first changes and commit after every task.

---

## File Structure

### Create

- `web/apps/console/src/presentation/evidence/evidence-model.ts`: safe projection from canonical `EvidenceRecord` values to receipt and inspector view data.
- `web/apps/console/src/presentation/evidence/evidence-model.test.ts`: projection, status extraction, malformed value, and empty-state tests.
- `web/apps/console/src/presentation/evidence/EvidenceReceipt.tsx`: compact bottom-row evidence affordance.
- `web/apps/console/src/presentation/evidence/EvidenceReceipt.test.tsx`: visible, disabled, status, count, and activation tests.
- `web/apps/console/src/presentation/evidence/EvidenceInspector.tsx`: modal interpreted/raw evidence inspection.
- `web/apps/console/src/presentation/evidence/EvidenceInspector.test.tsx`: tabs, record selection, focus, malformed raw value, and close tests.
- `web/apps/console/src/presentation/PresentationFooter.tsx`: stable composition of scene progress and evidence receipt.
- `web/apps/console/src/presentation/PresentationFooter.test.tsx`: footer composition and receipt visibility tests.

### Modify

- `web/apps/console/src/presentation/canvas-fit.ts`: return adaptive logical dimensions with scale and offsets.
- `web/apps/console/src/presentation/canvas-fit.test.ts`: pin supported and extreme aspect-ratio math.
- `web/apps/console/src/presentation/PresentationCanvas.tsx`: render the adaptive logical width.
- `web/apps/console/src/presentation/PresentationCanvas.test.tsx`: pin resize behavior at representative viewports.
- `web/apps/console/src/presentation/storyboard.ts`: replace `peek/open` beat vocabulary with `receipt` and prevent beats from requesting `inspector`.
- `web/apps/console/src/presentation/presentation-state.ts`: model transient inspector state and clear it on beat navigation.
- `web/apps/console/src/presentation/presentation-state.test.ts`: pin navigation, close priority, and receipt behavior.
- `web/apps/console/src/presentation/PresentationStage.tsx`: compose primary, footer, chat, and inspector without an evidence grid column.
- `web/apps/console/src/presentation/PresentationRoute.tsx`: dispatch `inspector` for explicit evidence actions.
- `web/apps/console/src/presentation/PresentationRoute.test.tsx`: verify no automatic dialog, explicit opening, and navigation closure.
- `web/apps/console/src/presentation/presentation.css`: replace drawer geometry with footer, overlay, and compact container-query rules.
- `web/apps/console/src/presentation/styles/editorial.css`: establish the named inline-size container on the logical canvas.
- `web/README.md`: document adaptive geometry and receipt/inspector behavior.
- `docs/current_roadmap.md`: mark this slice complete and link the archived plan.

### Delete

- `web/apps/console/src/presentation/EvidenceDrawer.tsx`
- `web/apps/console/src/presentation/EvidenceDrawer.test.tsx`

---

### Task 1: Adaptive Logical Canvas Geometry

**Files:**
- Modify: `web/apps/console/src/presentation/canvas-fit.ts`
- Modify: `web/apps/console/src/presentation/canvas-fit.test.ts`
- Modify: `web/apps/console/src/presentation/PresentationCanvas.tsx`
- Modify: `web/apps/console/src/presentation/PresentationCanvas.test.tsx`

**Interfaces:**
- Produces: `fitPresentationCanvas(viewport: ViewportSize): CanvasFit`
- Produces: `CanvasFit` with `logicalWidth`, `logicalHeight`, `scale`, `offsetX`, and `offsetY`
- Produces: `PRESENTATION_MIN_WIDTH = 960`, `PRESENTATION_MAX_WIDTH = 1280`, and `PRESENTATION_HEIGHT = 720`
- Consumes: browser `innerWidth` and `innerHeight`; no observer or persistent setting

- [ ] **Step 1: Replace fixed-fit expectations with adaptive math tests**

  Update `canvas-fit.test.ts` to assert exact dimensions and approximately equal floating-point scale values:

  ```ts
  import { describe, expect, it } from "vitest";
  import { fitPresentationCanvas } from "./canvas-fit.js";

  describe("fitPresentationCanvas", () => {
    it.each([
      [{ width: 1280, height: 720 }, 1280, 1, 0, 0],
      [{ width: 1024, height: 768 }, 960, 1024 / 960, 0, 0],
      [{ width: 1200, height: 800 }, 1080, 1200 / 1080, 0, 0],
      [{ width: 800, height: 800 }, 960, 800 / 960, 0, 100],
      [{ width: 1920, height: 720 }, 1280, 1, 320, 0],
    ])("fits %o into the supported logical ratio range", (
      viewport,
      logicalWidth,
      scale,
      offsetX,
      offsetY,
    ) => {
      const fit = fitPresentationCanvas(viewport);
      expect(fit.logicalWidth).toBe(logicalWidth);
      expect(fit.logicalHeight).toBe(720);
      expect(fit.scale).toBeCloseTo(scale);
      expect(fit.offsetX).toBeCloseTo(offsetX);
      expect(fit.offsetY).toBeCloseTo(offsetY);
    });

    it("returns the default logical size with zero scale before viewport measurement", () => {
      expect(fitPresentationCanvas({ width: 0, height: 0 })).toEqual({
        logicalWidth: 1280,
        logicalHeight: 720,
        scale: 0,
        offsetX: 0,
        offsetY: 0,
      });
    });
  });
  ```

- [ ] **Step 2: Run the geometry test and verify the red phase**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- canvas-fit.test.ts
  ```

  Expected: FAIL because `CanvasFit` does not expose logical dimensions and `1024x768` still produces the fixed-canvas `0.8` scale with `96px` vertical letterboxing.

- [ ] **Step 3: Implement clamped logical canvas math**

  Replace the fixed-width calculation in `canvas-fit.ts` with:

  ```ts
  export const PRESENTATION_MIN_WIDTH = 960;
  export const PRESENTATION_MAX_WIDTH = 1280;
  export const PRESENTATION_HEIGHT = 720;

  export type ViewportSize = {
    readonly width: number;
    readonly height: number;
  };

  export type CanvasFit = {
    readonly logicalWidth: number;
    readonly logicalHeight: number;
    readonly scale: number;
    readonly offsetX: number;
    readonly offsetY: number;
  };

  const clamp = (value: number, minimum: number, maximum: number): number =>
    Math.min(maximum, Math.max(minimum, value));

  export const fitPresentationCanvas = (viewport: ViewportSize): CanvasFit => {
    if (viewport.width <= 0 || viewport.height <= 0) {
      return {
        logicalWidth: PRESENTATION_MAX_WIDTH,
        logicalHeight: PRESENTATION_HEIGHT,
        scale: 0,
        offsetX: 0,
        offsetY: 0,
      };
    }

    // Width follows the viewport ratio only inside the reviewed 4:3-16:9 range.
    const logicalWidth = clamp(
      PRESENTATION_HEIGHT * (viewport.width / viewport.height),
      PRESENTATION_MIN_WIDTH,
      PRESENTATION_MAX_WIDTH,
    );
    const scale = Math.min(
      viewport.width / logicalWidth,
      viewport.height / PRESENTATION_HEIGHT,
    );
    return {
      logicalWidth,
      logicalHeight: PRESENTATION_HEIGHT,
      scale,
      offsetX: (viewport.width - logicalWidth * scale) / 2,
      offsetY: (viewport.height - PRESENTATION_HEIGHT * scale) / 2,
    };
  };
  ```

- [ ] **Step 4: Make `PresentationCanvas` consume returned dimensions**

  Remove `PRESENTATION_WIDTH` from the component import, update the comment to describe clamped adaptive geometry, and set:

  ```tsx
  style={{
    width: fit.logicalWidth,
    height: fit.logicalHeight,
    left: fit.offsetX,
    top: fit.offsetY,
    transform: `scale(${fit.scale})`,
  }}
  ```

  Do not add `ResizeObserver`. The logical canvas depends only on the viewport, so the existing `window.resize` listener is the correct ownership boundary.

- [ ] **Step 5: Update component resize tests**

  In `PresentationCanvas.test.tsx`, replace the fixed-canvas assertions with:

  ```tsx
  it("fills a 16:9 viewport with the maximum logical width", () => {
    setViewport(1280, 720);
    render(<PresentationCanvas><div>Scene</div></PresentationCanvas>);
    expect(screen.getByTestId("presentation-canvas")).toHaveStyle({
      width: "1280px",
      height: "720px",
      transform: "scale(1)",
      left: "0px",
      top: "0px",
    });
  });

  it("recomputes the logical width after resizing to 4:3", () => {
    setViewport(1280, 720);
    render(<PresentationCanvas><div>Scene</div></PresentationCanvas>);
    setViewport(1024, 768);
    act(() => window.dispatchEvent(new Event("resize")));
    const canvas = screen.getByTestId("presentation-canvas");
    expect(canvas).toHaveStyle({ width: "960px", height: "720px" });
    expect(canvas.style.left).toBe("0px");
    expect(canvas.style.top).toBe("0px");
    expect(Number(canvas.style.transform.match(/scale\((.+)\)/)?.[1])).toBeCloseTo(1024 / 960);
  });

  it("uses an intermediate logical width instead of selecting a preset", () => {
    setViewport(1200, 800);
    render(<PresentationCanvas><div>Scene</div></PresentationCanvas>);
    expect(screen.getByTestId("presentation-canvas")).toHaveStyle({
      width: "1080px",
      height: "720px",
    });
  });
  ```

- [ ] **Step 6: Run focused tests and commit**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- canvas-fit.test.ts PresentationCanvas.test.tsx
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: all focused tests pass and typecheck exits `0`.

  Commit:

  ```powershell
  git add web/apps/console/src/presentation/canvas-fit.ts web/apps/console/src/presentation/canvas-fit.test.ts web/apps/console/src/presentation/PresentationCanvas.tsx web/apps/console/src/presentation/PresentationCanvas.test.tsx
  git commit -m "feat: adapt presentation canvas ratio"
  ```

---

### Task 2: Semantic Evidence State and Navigation

**Files:**
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/presentation-state.ts`
- Modify: `web/apps/console/src/presentation/presentation-state.test.ts`
- Modify: `web/apps/console/src/presentation/scenes/ArchitectureScene.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/EvidenceDrawer.tsx`
- Modify: `web/apps/console/src/presentation/EvidenceDrawer.test.tsx`
- Modify: `web/apps/console/src/demo/agent/events.ts`
- Modify: `web/apps/console/src/demo/agent/recipes.ts`
- Modify: `web/apps/console/src/demo/agent/tools.ts`
- Modify: `web/apps/console/src/demo/agent/tools.test.ts`
- Modify: `web/apps/console/src/demo/agent/preparedRecipeDriver.ts`
- Modify: `web/apps/console/src/demo/agent/preparedRecipeDriver.test.ts`

**Interfaces:**
- Produces: `EvidencePresentation = "hidden" | "receipt" | "inspector"`
- Produces: `BeatEvidencePresentation = "hidden" | "receipt"`
- Produces: `set_evidence_presentation` reducer action
- Consumes: existing beat composition, navigation, and global `close_overlay`

- [ ] **Step 1: Write reducer tests for the new semantics**

  Replace the old `open/peek` assertions and add these cases in `presentation-state.test.ts`:

  ```ts
  it("derives a receipt from beat metadata without opening an inspector", () => {
    const state = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "architecture", beatId: "node-use", focusPath: ["node-use"] },
    });
    expect(compositionForState(state).evidencePresentation).toBe("receipt");
    expect(state.evidencePresentationOverride).toBeNull();
  });

  it("closes an explicit inspector before the node spotlight", () => {
    const withNode = presentationReducer(initialPresentationState, {
      type: "select_node",
      nodeId: "review_issues",
    });
    const withInspector = presentationReducer(withNode, {
      type: "set_evidence_presentation",
      presentation: "inspector",
    });
    const firstEscape = presentationReducer(withInspector, { type: "close_overlay" });
    expect(firstEscape.evidencePresentationOverride).toBe("hidden");
    expect(firstEscape.selectedNodeId).toBe("review_issues");
    const secondEscape = presentationReducer(firstEscape, { type: "close_overlay" });
    expect(secondEscape.selectedNodeId).toBeNull();
  });

  it("closes the inspector and recomputes receipt state when the beat changes", () => {
    const atReceiptBeat = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "architecture", beatId: "node-use", focusPath: ["node-use"] },
    });
    const opened = presentationReducer(atReceiptBeat, {
      type: "set_evidence_presentation",
      presentation: "inspector",
    });
    const advanced = presentationReducer(opened, { type: "next" });
    expect(advanced.evidencePresentationOverride).toBeNull();
    expect(compositionForState(advanced).evidencePresentation).not.toBe("inspector");
  });

  it("does not treat a receipt as an Escape-closeable overlay", () => {
    const receipt = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "authoring", beatId: "diagnose", focusPath: [] },
    });
    expect(presentationReducer(receipt, { type: "close_overlay" })).toEqual(receipt);
  });
  ```

  Update the prepared-agent expectations before implementation so the recipe
  ends at trace evidence without opening presentation chrome:

  ```ts
  expect(toolNames).toEqual([
    "inspectDeployment",
    "startPreparedReportRun",
    "selectWorkflowNode",
    "resumeIssueReview",
    "readRunTrace",
  ]);

  expect(isAllowedAgentToolName("openEvidence")).toBe(false);
  ```

- [ ] **Step 2: Run the reducer test and verify the red phase**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- presentation-state.test.ts preparedRecipeDriver.test.ts tools.test.ts
  ```

  Expected: FAIL because the new type names, action, and composition property do not exist, and the prepared recipe still emits `openEvidence`.

- [ ] **Step 3: Replace geometric evidence vocabulary in the storyboard**

  In `storyboard.ts`, define separate beat and runtime types:

  ```ts
  export type EvidencePresentation = "hidden" | "receipt" | "inspector";
  export type BeatEvidencePresentation = Exclude<EvidencePresentation, "inspector">;

  export type SceneBeatDefinition = {
    readonly id: string;
    readonly title: string;
    readonly caption: string;
    readonly chatMode: ChatMode;
    readonly chatTheme: ChatTheme;
    readonly evidencePresentation: BeatEvidencePresentation;
    readonly figure: FigureBeatDefinition | null;
  };
  ```

  Rename the beat option and constructor default from `evidenceMode` to `evidencePresentation`. Change the `node-use` and `diagnose` beats from `peek` to `receipt`. Change the `trace` beat from `open` to `receipt`; detailed evidence must no longer auto-open on navigation.

  Update `ArchitectureScene.test.tsx` fixture data to use `evidencePresentation: "hidden"`.

- [ ] **Step 4: Migrate reducer state and clear transient inspection on navigation**

  In `presentation-state.ts`:

  ```ts
  readonly evidencePresentationOverride: EvidencePresentation | null;
  ```

  Rename the action to:

  ```ts
  | {
      readonly type: "set_evidence_presentation";
      readonly presentation: EvidencePresentation;
    }
  ```

  Return `evidencePresentation` from `compositionForState`. Add a small helper used by `next`, `previous`, `jump`, `jump_hash`, `open_discussion`, and `close_discussion`:

  ```ts
  const moveToLocation = (
    state: PresentationState,
    location: PresentationLocation,
  ): PresentationState => ({
    ...state,
    location,
    evidencePresentationOverride: null,
  });
  ```

  Preserve `set_focus_path` without clearing evidence because it changes figure focus, not the current beat. In `close_overlay`, close an explicit inspector first, then `selectedNodeId`, then a discussion. Do not hide a receipt on `Escape`.

- [ ] **Step 5: Search for and remove old internal vocabulary**

  Run:

  ```powershell
  rg -n 'EvidenceMode|evidenceMode|evidenceModeOverride|set_evidence_mode|evidenceMode: "(peek|open)"' web/apps/console/src/presentation
  ```

  Update every presentation caller and test found by the search to the semantic names. In `PresentationRoute.tsx`, the explicit `openEvidence` callback passed to `PresentationStage` dispatches:

  ```ts
  dispatch({
    type: "set_evidence_presentation",
    presentation: "inspector",
  });
  ```

  In `PresentationStage.tsx`, consume `composition.evidencePresentation` and expose `data-evidence-presentation`. Temporarily pass the semantic presentation value to `EvidenceDrawer`; it still renders every non-hidden value until Task 5 removes it. Update `EvidenceDrawer`'s prop type to `EvidencePresentation`.

  Remove the prepared recipe's final `open-evidence` step and remove
  `openEvidence` from `RecipeTool`, `PresentationToolAction`,
  `PresentationToolName`, `AGENT_TOOLS`, and the driver switch. Remove the
  corresponding `PresentationRoute` pending-action case. The trace beat's
  receipt is the automatic affordance; only the footer or operation button may
  open the inspector. Do not retain aliases for either old internal contract.

  Confirm the prepared-agent surface is clean:

  ```powershell
  rg -n -F 'openEvidence' web/apps/console/src/demo/agent
  ```

  Expected: no matches. Presentation component callbacks named `openEvidence`
  remain valid because they represent explicit human controls, not agent tools.

- [ ] **Step 6: Run focused tests and commit**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- presentation-state.test.ts storyboard.test.ts ArchitectureScene.test.tsx preparedRecipeDriver.test.ts tools.test.ts
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: focused tests pass and typecheck exits `0`.

  Commit:

  ```powershell
  git add web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/presentation-state.ts web/apps/console/src/presentation/presentation-state.test.ts web/apps/console/src/presentation/scenes/ArchitectureScene.test.tsx web/apps/console/src/presentation/PresentationRoute.tsx web/apps/console/src/presentation/PresentationStage.tsx web/apps/console/src/presentation/EvidenceDrawer.tsx web/apps/console/src/presentation/EvidenceDrawer.test.tsx web/apps/console/src/demo/agent
  git commit -m "refactor: name presentation evidence states"
  ```

---

### Task 3: Evidence Projection and Bottom-Row Receipt

**Files:**
- Create: `web/apps/console/src/presentation/evidence/evidence-model.ts`
- Create: `web/apps/console/src/presentation/evidence/evidence-model.test.ts`
- Create: `web/apps/console/src/presentation/evidence/EvidenceReceipt.tsx`
- Create: `web/apps/console/src/presentation/evidence/EvidenceReceipt.test.tsx`
- Create: `web/apps/console/src/presentation/PresentationFooter.tsx`
- Create: `web/apps/console/src/presentation/PresentationFooter.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneProgress.tsx`

**Interfaces:**
- Produces: `projectEvidenceReceipt(records: readonly EvidenceRecord[]): EvidenceReceiptModel`
- Produces: `projectEvidenceDetail(record: EvidenceRecord): EvidenceDetailModel`
- Produces: `formatEvidenceValue(value: unknown): FormattedEvidenceValue`
- Produces: `EvidenceReceipt` and `PresentationFooter`
- Consumes: canonical `EvidenceRecord[]`; latest record wins for the compact receipt

- [ ] **Step 1: Write safe projection tests**

  Create `evidence-model.test.ts` with cases for a normal result, no records, missing status, and cyclic raw data:

  ```ts
  import { describe, expect, it } from "vitest";
  import type { EvidenceRecord } from "../../app/state.js";
  import {
    formatEvidenceValue,
    projectEvidenceDetail,
    projectEvidenceReceipt,
  } from "./evidence-model.js";

  const record = (response: unknown): EvidenceRecord => ({
    id: "run-start",
    operation: "workflow.runs.start",
    label: "Start run",
    equivalentCli: "uv run wf run start demo.default",
    request: { deployment_id: "demo.default" },
    response,
    durationMs: 88,
  });

  describe("evidence projection", () => {
    it("uses the latest record and extracts a nested result status", () => {
      const model = projectEvidenceReceipt([
        record({ result: { status: "interrupted" } }),
        { ...record({ result: { status: "completed" } }), id: "trace", operation: "workflow.runs.trace" },
      ]);
      expect(model).toMatchObject({
        available: true,
        operation: "workflow.runs.trace",
        status: "completed",
        recordCount: 2,
      });
    });

    it("returns an unavailable receipt for no records", () => {
      expect(projectEvidenceReceipt([])).toEqual({
        available: false,
        operation: "Evidence unavailable",
        status: null,
        recordCount: 0,
      });
    });

    it("projects run and deployment identifiers without requiring status", () => {
      expect(projectEvidenceDetail({
        ...record({ result: { run_id: "run_demo" } }),
        request: { deployment_id: "demo.default" },
      })).toMatchObject({
        status: null,
        durationMs: 88,
        deploymentId: "demo.default",
        runId: "run_demo",
        equivalentCli: "uv run wf run start demo.default",
      });
    });

    it("returns bounded text and a note when raw evidence is not JSON serializable", () => {
      const cyclic: Record<string, unknown> = {};
      cyclic.self = cyclic;
      const formatted = formatEvidenceValue(cyclic);
      expect(formatted.text).toBe("[object Object]");
      expect(formatted.note).toMatch(/could not format as json/i);
    });

    it("truncates oversized evidence before it reaches the inspector", () => {
      const formatted = formatEvidenceValue("x".repeat(120_000));
      expect(formatted.text.length).toBeLessThanOrEqual(100_003);
      expect(formatted.note).toMatch(/truncated/i);
    });
  });
  ```

- [ ] **Step 2: Run the model test and verify the red phase**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- evidence-model.test.ts
  ```

  Expected: FAIL because the model module does not exist.

- [ ] **Step 3: Implement narrow projection helpers**

  Create `evidence-model.ts` with exported readonly model types. Use a guarded object helper to read `response.result.status`; do not assume the response shape or cast the complete payload.

  ```ts
  import type { EvidenceRecord } from "../../app/state.js";

  export type EvidenceReceiptModel = {
    readonly available: boolean;
    readonly operation: string;
    readonly status: string | null;
    readonly recordCount: number;
  };

  export type EvidenceDetailModel = EvidenceReceiptModel & {
    readonly id: string;
    readonly label: string;
    readonly equivalentCli: string;
    readonly durationMs: number;
    readonly deploymentId: string | null;
    readonly runId: string | null;
    readonly request: FormattedEvidenceValue;
    readonly response: FormattedEvidenceValue;
  };

  export type FormattedEvidenceValue = {
    readonly text: string;
    readonly note: string | null;
  };

  const MAX_EVIDENCE_TEXT_LENGTH = 100_000;

  const objectValue = (value: unknown): Readonly<Record<string, unknown>> | null =>
    typeof value === "object" && value !== null && !Array.isArray(value)
      ? value as Readonly<Record<string, unknown>>
      : null;

  const responseStatus = (response: unknown): string | null => {
    const result = objectValue(objectValue(response)?.result);
    return typeof result?.status === "string" ? result.status : null;
  };

  const stringField = (
    value: Readonly<Record<string, unknown>> | null,
    field: string,
  ): string | null => {
    const candidate = value?.[field];
    return typeof candidate === "string" ? candidate : null;
  };

  const boundEvidenceText = (
    text: string,
    note: string | null,
  ): FormattedEvidenceValue => {
    if (text.length <= MAX_EVIDENCE_TEXT_LENGTH) return { text, note };
    const truncation = `Evidence truncated to ${MAX_EVIDENCE_TEXT_LENGTH} characters.`;
    return {
      text: `${text.slice(0, MAX_EVIDENCE_TEXT_LENGTH)}...`,
      note: note ? `${note} ${truncation}` : truncation,
    };
  };

  export const formatEvidenceValue = (value: unknown): FormattedEvidenceValue => {
    try {
      const encoded = JSON.stringify(value, null, 2);
      return boundEvidenceText(encoded ?? String(value), null);
    } catch {
      let text: string;
      try {
        text = String(value);
      } catch {
        text = "[Unprintable evidence]";
      }
      return boundEvidenceText(
        text,
        "Could not format as JSON; showing a bounded text representation.",
      );
    }
  };

  export const projectEvidenceReceipt = (
    records: readonly EvidenceRecord[],
  ): EvidenceReceiptModel => {
    const latest = records.at(-1);
    if (!latest) {
      return { available: false, operation: "Evidence unavailable", status: null, recordCount: 0 };
    }
    return {
      available: true,
      operation: latest.operation,
      status: responseStatus(latest.response),
      recordCount: records.length,
    };
  };

  export const projectEvidenceDetail = (record: EvidenceRecord): EvidenceDetailModel => {
    const request = objectValue(record.request);
    const result = objectValue(objectValue(record.response)?.result);
    return {
      ...projectEvidenceReceipt([record]),
      id: record.id,
      label: record.label,
      equivalentCli: record.equivalentCli,
      durationMs: record.durationMs,
      deploymentId: stringField(result, "deployment_id") ?? stringField(request, "deployment_id"),
      runId: stringField(result, "run_id") ?? stringField(request, "run_id"),
      request: formatEvidenceValue(record.request),
      response: formatEvidenceValue(record.response),
    };
  };
  ```

  The cast is limited to the guarded object helper. Add a comment there if the final implementation uses a less obvious schema guard.

- [ ] **Step 4: Write receipt and footer tests**

  Define a local fixture in `EvidenceReceipt.test.tsx`:

  ```ts
  const record: EvidenceRecord = {
    id: "run-start",
    operation: "workflow.runs.start",
    label: "Start run",
    equivalentCli: "uv run wf run start demo.default",
    request: { deployment_id: "demo.default" },
    response: { result: { status: "interrupted", run_id: "run_demo" } },
    durationMs: 88,
  };
  ```

  Then verify:

  ```tsx
  it("shows latest operation, status, count, and opens inspection", async () => {
    const inspect = vi.fn();
    render(<EvidenceReceipt records={[record]} visible onInspect={inspect} />);
    expect(screen.getByText("workflow.runs.start")).toBeInTheDocument();
    expect(screen.getByText("interrupted")).toBeInTheDocument();
    expect(screen.getByText(/1 record/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /inspect evidence/i }));
    expect(inspect).toHaveBeenCalledOnce();
  });

  it("renders no receipt when the beat keeps evidence hidden", () => {
    render(<EvidenceReceipt records={[record]} visible={false} onInspect={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /inspect evidence/i })).not.toBeInTheDocument();
  });

  it("disables inspection when evidence is unavailable", () => {
    render(<EvidenceReceipt records={[]} visible onInspect={vi.fn()} />);
    expect(screen.getByRole("button", { name: /inspect evidence/i })).toBeDisabled();
  });
  ```

  In `PresentationFooter.test.tsx`, use a complete local record and verify both
  progress and provenance occupy one footer:

  ```tsx
  it("combines scene progress and evidence provenance", () => {
    const evidence: EvidenceRecord = {
      id: "trace",
      operation: "workflow.runs.trace",
      label: "Inspect trace",
      equivalentCli: "uv run wf run trace run_demo",
      request: { run_id: "run_demo" },
      response: { result: { status: "completed" } },
      durationMs: 34,
    };
    render(
      <PresentationFooter
        location={{
          kind: "main",
          sceneId: "architecture",
          beatId: "runtime",
          focusPath: [],
        }}
        evidence={[evidence]}
        showEvidenceReceipt
        inspectEvidence={vi.fn()}
      />,
    );
    const footer = screen.getByRole("contentinfo", { name: /presentation footer/i });
    expect(within(footer).getByText("6 / 12")).toBeInTheDocument();
    expect(within(footer).getByText("3 / 4")).toBeInTheDocument();
    expect(within(footer).getByText("workflow.runs.trace")).toBeInTheDocument();
  });
  ```

- [ ] **Step 5: Run component tests and verify the red phase**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- EvidenceReceipt.test.tsx PresentationFooter.test.tsx
  ```

  Expected: FAIL because both components do not exist.

- [ ] **Step 6: Implement the receipt and footer**

  `EvidenceReceipt` accepts:

  ```ts
  type EvidenceReceiptProps = {
    readonly records: readonly EvidenceRecord[];
    readonly visible: boolean;
    readonly onInspect: () => void;
  };
  ```

  Render one button with accessible name `Inspect evidence`. Use `projectEvidenceReceipt`; do not inspect response objects in JSX:

  ```tsx
  export const EvidenceReceipt = ({
    records,
    visible,
    onInspect,
  }: EvidenceReceiptProps) => {
    if (!visible) return null;
    const receipt = projectEvidenceReceipt(records);
    const countLabel = `${receipt.recordCount} ${receipt.recordCount === 1 ? "record" : "records"}`;
    return (
      <button
        type="button"
        className="evidence-receipt"
        aria-label="Inspect evidence"
        disabled={!receipt.available}
        onClick={onInspect}
      >
        <span>Evidence: {receipt.operation}</span>
        {receipt.status && <span data-status={receipt.status}>{receipt.status}</span>}
        <span>{countLabel}</span>
        {receipt.available && <span aria-hidden="true">Inspect</span>}
      </button>
    );
  };
  ```

  `PresentationFooter` accepts:

  ```ts
  type PresentationFooterProps = {
    readonly location: MainLocation;
    readonly evidence: readonly EvidenceRecord[];
    readonly showEvidenceReceipt: boolean;
    readonly inspectEvidence: () => void;
  };
  ```

  Render `<SceneProgress>` and `<EvidenceReceipt>` inside one footer. Keep `SceneProgress` responsible only for scene and beat numbering:

  ```tsx
  export const PresentationFooter = ({
    location,
    evidence,
    showEvidenceReceipt,
    inspectEvidence,
  }: PresentationFooterProps) => (
    <footer className="presentation-footer" aria-label="presentation footer">
      <SceneProgress location={location} />
      <EvidenceReceipt
        records={evidence}
        visible={showEvidenceReceipt}
        onInspect={inspectEvidence}
      />
    </footer>
  );
  ```

- [ ] **Step 7: Run focused tests and commit**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- evidence-model.test.ts EvidenceReceipt.test.tsx PresentationFooter.test.tsx SceneProgress.test.tsx
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: all focused tests pass and typecheck exits `0`.

  Commit:

  ```powershell
  git add web/apps/console/src/presentation/evidence web/apps/console/src/presentation/PresentationFooter.tsx web/apps/console/src/presentation/PresentationFooter.test.tsx web/apps/console/src/presentation/SceneProgress.tsx
  git commit -m "feat: add presentation evidence receipt"
  ```

---

### Task 4: Accessible Centered Evidence Inspector

**Files:**
- Create: `web/apps/console/src/presentation/evidence/EvidenceInspector.tsx`
- Create: `web/apps/console/src/presentation/evidence/EvidenceInspector.test.tsx`

**Interfaces:**
- Produces: `EvidenceInspector`
- Consumes: `records`, `open`, and `onClose`
- Consumes: `projectEvidenceDetail` from Task 3
- Owns: selected record and `interpreted/raw` local view state

```ts
type EvidenceInspectorProps = {
  readonly records: readonly EvidenceRecord[];
  readonly open: boolean;
  readonly onClose: () => void;
};
```

- [ ] **Step 1: Write inspector behavior tests**

  Define complete local records in `EvidenceInspector.test.tsx`:

  ```ts
  const record: EvidenceRecord = {
    id: "run-start",
    operation: "workflow.runs.start",
    label: "Start run",
    equivalentCli: "uv run wf run start demo.default",
    request: { deployment_id: "demo.default" },
    response: { result: { status: "interrupted", run_id: "run_demo" } },
    durationMs: 88,
  };

  const traceRecord: EvidenceRecord = {
    ...record,
    id: "run-trace",
    operation: "workflow.runs.trace",
    label: "Inspect trace",
    equivalentCli: "uv run wf run trace run_demo",
    response: { result: { status: "completed", frames: [] } },
    durationMs: 34,
  };
  ```

  Create tests for interpreted-first rendering, raw switching, record stability, focus restoration, close, and malformed data:

  ```tsx
  it("opens on interpreted evidence and switches to raw request and response", async () => {
    render(<EvidenceInspector records={[record]} open onClose={vi.fn()} />);
    expect(screen.getByRole("dialog", { name: /evidence inspector/i })).toBeInTheDocument();
    expect(screen.getByText("workflow.runs.start")).toBeInTheDocument();
    expect(screen.getByText("88 ms")).toBeInTheDocument();
    expect(screen.getByText("demo.default")).toBeInTheDocument();
    expect(screen.getByText("run_demo")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /raw/i }));
    expect(screen.getByText(/uv run wf run start/i)).toBeInTheDocument();
    expect(screen.getByText(/deployment_id/i)).toBeInTheDocument();
    expect(screen.getByText(/interrupted/i)).toBeInTheDocument();
  });

  it("keeps the selected record while changing views", async () => {
    render(<EvidenceInspector records={[record, traceRecord]} open onClose={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText(/evidence record/i), record.id);
    await userEvent.click(screen.getByRole("tab", { name: /raw/i }));
    expect(screen.getByLabelText(/evidence record/i)).toHaveValue(record.id);
  });

  it("focuses close on open and restores the previous trigger on unmount", () => {
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();
    const view = render(<EvidenceInspector records={[record]} open onClose={vi.fn()} />);
    expect(screen.getByRole("button", { name: /close evidence/i })).toHaveFocus();
    view.unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });
  ```

  Add explicit focus-wrap, empty-state, and malformed-value tests:

  ```tsx
  it("wraps keyboard focus inside the inspector", async () => {
    render(<EvidenceInspector records={[record]} open onClose={vi.fn()} />);
    const close = screen.getByRole("button", { name: /close evidence/i });
    const raw = screen.getByRole("tab", { name: /raw/i });
    close.focus();
    await userEvent.tab({ shift: true });
    expect(raw).toHaveFocus();
    await userEvent.tab();
    expect(close).toHaveFocus();
  });

  it("renders a bounded unavailable state with no records", () => {
    render(<EvidenceInspector records={[]} open onClose={vi.fn()} />);
    expect(screen.getByText(/evidence unavailable/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/evidence record/i)).not.toBeInTheDocument();
  });

  it("shows a formatting note for non-serializable raw evidence", async () => {
    const cyclic: Record<string, unknown> = {};
    cyclic.self = cyclic;
    render(<EvidenceInspector records={[{ ...record, response: cyclic }]} open onClose={vi.fn()} />);
    await userEvent.click(screen.getByRole("tab", { name: /raw/i }));
    expect(screen.getByText(/could not format as json/i)).toBeInTheDocument();
  });
  ```

- [ ] **Step 2: Run the inspector test and verify the red phase**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- EvidenceInspector.test.tsx
  ```

  Expected: FAIL because `EvidenceInspector` does not exist.

- [ ] **Step 3: Implement modal semantics without a new dependency**

  Import `useEffect`, `useRef`, `useState`, and React's `KeyboardEvent` type:

  ```ts
  import { useEffect, useRef, useState, type KeyboardEvent } from "react";
  ```

  Initialize the local selection and view from the latest record:

  ```ts
  const [view, setView] = useState<"interpreted" | "raw">("interpreted");
  const [selectedRecordId, setSelectedRecordId] = useState(
    () => records.at(-1)?.id ?? "",
  );
  const selectedRecord = records.find((record) => record.id === selectedRecordId)
    ?? records.at(-1)
    ?? null;
  const detail = selectedRecord ? projectEvidenceDetail(selectedRecord) : null;
  ```

  Preserve `selectedRecordId` while it remains present and switch to the latest
  record only when the current record disappears:

  ```ts
  useEffect(() => {
    setSelectedRecordId((current) =>
      records.some((record) => record.id === current)
        ? current
        : records.at(-1)?.id ?? "",
    );
  }, [records]);
  ```

  After all hooks, return `null` when `open` is false. Then use a stage-local overlay:

  ```ts
  if (!open) return null;
  ```

  ```tsx
  <div className="evidence-inspector-layer">
    <section
      ref={dialogRef}
      className="evidence-inspector"
      role="dialog"
      aria-modal="true"
      aria-label="Evidence inspector"
      onKeyDown={trapTabWithinDialog}
    >
      <header>
        <h2>Evidence</h2>
        <button ref={closeButtonRef} type="button" onClick={onClose}>
          Close evidence
        </button>
      </header>
      {selectedRecord && (
        <label>
          Evidence record
          <select
            value={selectedRecord.id}
            onChange={(event) => setSelectedRecordId(event.currentTarget.value)}
          >
            {records.map((record) => (
              <option key={record.id} value={record.id}>{record.operation}</option>
            ))}
          </select>
        </label>
      )}
      <div role="tablist" aria-label="Evidence view">
        <button role="tab" aria-selected={view === "interpreted"} onClick={() => setView("interpreted")}>
          Interpreted
        </button>
        <button role="tab" aria-selected={view === "raw"} onClick={() => setView("raw")}>
          Raw
        </button>
      </div>
      <div className="evidence-inspector__body">
        {!detail ? (
          <p>Evidence unavailable</p>
        ) : view === "interpreted" ? (
          <dl>
            <dt>Operation</dt><dd>{detail.operation}</dd>
            <dt>Status</dt><dd>{detail.status ?? "Unavailable"}</dd>
            <dt>Duration</dt><dd>{detail.durationMs} ms</dd>
            <dt>Deployment</dt><dd>{detail.deploymentId ?? "Unavailable"}</dd>
            <dt>Run</dt><dd>{detail.runId ?? "Unavailable"}</dd>
          </dl>
        ) : (
          <>
            <h3>Equivalent CLI</h3><pre><code>{detail.equivalentCli}</code></pre>
            <h3>Request</h3><pre><code>{detail.request.text}</code></pre>
            {detail.request.note && <p>{detail.request.note}</p>}
            <h3>Response</h3><pre><code>{detail.response.text}</code></pre>
            {detail.response.note && <p>{detail.response.note}</p>}
          </>
        )}
      </div>
    </section>
  </div>
  ```

  Keep the focus lifecycle explicit:

  ```ts
  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    closeButtonRef.current?.focus();
    return () => previouslyFocused?.focus();
  }, [open]);
  ```

  Keep the Tab trap local and bounded to the dialog:

  ```ts
  const trapTabWithinDialog = (event: KeyboardEvent<HTMLElement>) => {
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
  ```

  The global `PresentationRoute` Escape listener remains the single Escape owner. The inspector traps only Tab. Handling Escape locally as well would dispatch two closes and could accidentally close the node spotlight or discussion behind it.

  Initialize selection to the latest record. When `records` changes, preserve the selected id if it still exists; otherwise select the latest available record. Use two tabs, `Interpreted` and `Raw`. The raw view shows equivalent CLI, request, and response with the formatting note beside malformed values.

- [ ] **Step 4: Bound inspector content**

  Ensure raw evidence never expands the dialog beyond the stage:

  ```tsx
  <div className="evidence-inspector__body">
    <pre><code>{detail.request.text}</code></pre>
    <pre><code>{detail.response.text}</code></pre>
  </div>
  ```

  CSS ownership arrives in Task 5, but the DOM must expose stable classes and semantic headings for `Equivalent CLI`, `Request`, and `Response`.

- [ ] **Step 5: Run focused tests and commit**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- EvidenceInspector.test.tsx evidence-model.test.ts
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: inspector tests pass and typecheck exits `0`.

  Commit:

  ```powershell
  git add web/apps/console/src/presentation/evidence/EvidenceInspector.tsx web/apps/console/src/presentation/evidence/EvidenceInspector.test.tsx
  git commit -m "feat: add presentation evidence inspector"
  ```

---

### Task 5: Stage Composition and Compact Container Queries

**Files:**
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`
- Modify: `web/apps/console/src/presentation/styles/editorial.css`
- Delete: `web/apps/console/src/presentation/EvidenceDrawer.tsx`
- Delete: `web/apps/console/src/presentation/EvidenceDrawer.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Consumes: `PresentationFooter` and `EvidenceInspector`
- Consumes: semantic `composition.evidencePresentation`
- Produces: one primary grid region, one footer row, and transient overlays
- Produces: named `presentation-canvas` inline-size container

- [ ] **Step 1: Write structural integration tests**

  Update the stable-region test in `PresentationRoute.test.tsx`:

  ```tsx
  it("renders stable chat, primary, progress, and transient evidence surfaces", () => {
    render(<PresentationRoute />);
    expect(screen.getByLabelText(/agent chat region/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/primary presentation region/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/presentation footer/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/evidence region/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: /evidence inspector/i })).not.toBeInTheDocument();
  });
  ```

  Add a trace-beat test asserting the receipt is present but the inspector is not:

  ```tsx
  it("shows a receipt without auto-opening evidence on an evidence beat", () => {
    window.location.hash = "#scene/interrupt-evidence/trace";
    render(<PresentationRoute />);
    expect(screen.getByRole("button", { name: /inspect evidence/i })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: /evidence inspector/i })).not.toBeInTheDocument();
  });
  ```

  Add explicit opening and navigation tests in the same file:

  ```tsx
  // Add `act` to the existing Testing Library import.
  it("opens the inspector from an explicit operation action", async () => {
    window.location.hash = "#scene/workflow-demo/operation";
    render(<PresentationRoute />);
    await userEvent.click(await screen.findByRole("button", { name: /view raw evidence/i }));
    expect(screen.getByRole("dialog", { name: /evidence inspector/i })).toBeInTheDocument();
  });

  it("closes the inspector when navigation moves to another beat", async () => {
    window.location.hash = "#scene/workflow-demo/operation";
    render(<PresentationRoute />);
    await userEvent.click(await screen.findByRole("button", { name: /view raw evidence/i }));
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    });
    expect(screen.queryByRole("dialog", { name: /evidence inspector/i })).not.toBeInTheDocument();
  });
  ```

  Dispatching on `window` models presenter navigation outside an interactive inspector control. The route deliberately ignores advance keys originating inside a button, tab, select, or raw-evidence control.

- [ ] **Step 2: Run the route tests and verify the red phase**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- PresentationRoute.test.tsx
  ```

  Expected: FAIL because the old evidence region remains and the `trace` beat still renders drawer behavior.

- [ ] **Step 3: Replace the evidence column in `PresentationStage`**

  Remove `EvidenceDrawer` and the `.presentation-stage__evidence` aside. After the primary section, render:

  ```tsx
  {state.location.kind === "main" && (
    <PresentationFooter
      location={state.location}
      evidence={evidence}
      showEvidenceReceipt={composition.evidencePresentation !== "hidden"}
      inspectEvidence={openEvidence}
    />
  )}
  <EvidenceInspector
    records={evidence}
    open={composition.evidencePresentation === "inspector"}
    onClose={closeOverlay}
  />
  ```

  Rename the stage data attribute to `data-evidence-presentation`. Delete `EvidenceDrawer.tsx` and its test after no imports remain.

- [ ] **Step 4: Establish the container-query owner**

  In `styles/editorial.css`, add:

  ```css
  .presentation-canvas {
    container-name: presentation-canvas;
    container-type: inline-size;
  }
  ```

  Container queries apply to descendants, not the container itself. Keep adaptive width on `.presentation-canvas` and query its child `.presentation-stage`.

- [ ] **Step 5: Replace evidence-width grid geometry**

  In `presentation.css`, remove `--evidence-width`, `[data-evidence-mode]`, `.presentation-stage__evidence`, and `.evidence-drawer` rules. The stage becomes:

  ```css
  .presentation-stage {
    position: relative;
    width: 100%;
    height: 100%;
    min-width: 0;
    min-height: 0;
    display: grid;
    grid-template:
      "chat primary" minmax(0, 1fr)
      "footer footer" auto /
      var(--chat-width) minmax(0, 1fr);
  }

  .presentation-stage[data-chat-mode="hidden"] {
    grid-template:
      "primary" minmax(0, 1fr)
      "footer" auto /
      minmax(0, 1fr);
  }

  .presentation-stage__chat { grid-area: chat; }
  .presentation-stage__primary { grid-area: primary; }
  .presentation-footer { grid-area: footer; }
  ```

  Replace `height: 100dvh` on the stage with `height: 100%`. The stage is inside a transformed logical canvas; viewport units would bypass that ownership and are a common cause of 4:3 overflow.

- [ ] **Step 6: Add compact chat behavior and inspector precedence**

  Add:

  ```css
  @container presentation-canvas (max-width: 1080px) {
    .presentation-stage {
      grid-template:
        "primary" minmax(0, 1fr)
        "footer" auto /
        minmax(0, 1fr);
    }

    .presentation-stage__chat {
      position: absolute;
      inset: 0 auto var(--presentation-footer-height, 2.5rem) 0;
      width: min(18rem, 44%);
      z-index: 20;
    }

    .presentation-stage[data-evidence-presentation="inspector"] .presentation-stage__chat {
      visibility: hidden;
      pointer-events: none;
    }
  }
  ```

  The threshold is a visual tuning constant, not a second state model. Do not read container width in React.

- [ ] **Step 7: Style receipt and inspector without changing scene visuals**

  Add a stable footer and overlay geometry. Adapt colors to the existing presentation tokens, but preserve these dimensions and ownership rules:

  ```css
  .presentation-stage {
    --presentation-footer-height: 2.5rem;
  }

  .presentation-footer {
    min-height: var(--presentation-footer-height);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.35rem 1rem;
    border-top: 1px solid var(--stage-line);
    overflow: hidden;
  }

  .presentation-footer .scene-progress {
    flex: 0 0 auto;
    padding: 0;
  }

  .evidence-receipt {
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.65rem;
    border: 0;
    background: transparent;
    color: var(--text-secondary);
    font: 600 0.72rem/1.2 var(--font-evidence, monospace);
    cursor: pointer;
  }

  .evidence-receipt > :first-child {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .evidence-receipt:disabled {
    cursor: default;
    opacity: 0.65;
  }

  .evidence-receipt:focus-visible,
  .evidence-inspector button:focus-visible,
  .evidence-inspector select:focus-visible {
    outline: 2px solid var(--accent-cyan);
    outline-offset: 2px;
  }

  .evidence-inspector-layer {
    box-sizing: border-box;
    position: absolute;
    inset: 0;
    z-index: 30;
    display: grid;
    place-items: center;
    padding: 2.5rem 5%;
    background: oklch(0.08 0.02 250 / 0.68);
  }

  .evidence-inspector {
    box-sizing: border-box;
    width: min(70cqi, 56rem);
    max-width: calc(100% - 2rem);
    max-height: calc(100% - var(--presentation-footer-height));
    min-height: 0;
    display: grid;
    grid-template-rows: auto auto minmax(0, 1fr);
    overflow: hidden;
    border: 1px solid var(--stage-line);
    background: var(--stage-surface);
    color: var(--text-primary);
  }

  .evidence-inspector__body {
    min-height: 0;
    overflow: auto;
    padding: 1rem;
  }

  .evidence-inspector pre {
    max-width: 100%;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  ```

  Add a short opacity transition to `.evidence-inspector-layer`; the existing reduced-motion selectors must collapse it to effectively immediate. Do not animate stage grid dimensions or primary width.

  Do not adjust `.interactive-figure`, React Flow nodes, Dagre layout, `.workflow-graph-stage`, scene caption sizes, or graph-specific overflow in this task.

- [ ] **Step 8: Run focused tests and commit**

  Run:

  ```powershell
  pnpm --dir web --filter @lda/console test -- PresentationRoute.test.tsx PresentationFooter.test.tsx EvidenceReceipt.test.tsx EvidenceInspector.test.tsx
  pnpm --dir web --filter @lda/console typecheck
  ```

  Expected: focused tests pass and typecheck exits `0`.

  Confirm the old implementation is gone:

  ```powershell
  rg -n 'EvidenceDrawer|evidence-drawer|evidence-width|data-evidence-mode' web/apps/console/src/presentation
  ```

  Expected: no matches.

  Commit:

  ```powershell
  git add web/apps/console/src/presentation
  git commit -m "feat: replace presentation evidence drawer"
  ```

---

### Task 6: Browser Geometry and Review Runbook

**Files:**
- Modify: `docs/runbooks/presentation-visual-review.md`

**Interfaces:**
- Documents: repeatable adaptive-canvas and evidence-inspector browser checks
- Verifies: real browser geometry at three viewport ratios
- Preserves: screenshots as ignored review artifacts rather than committed product files

- [ ] **Step 1: Replace fixed-canvas runbook assumptions with the adaptive matrix**

  Replace the runbook's single-viewport introduction and its first two fixed-canvas checklist items. Keep the existing architecture and console review states, then add the evidence route and matrix:

  ```markdown
  ## Adaptive Canvas Matrix

  Review these routes at `1024x768`, `1200x800`, and `1280x720`, always at 100%
  browser zoom:

  1. `/present#scene/architecture/node-use/focus/node-use`
  2. `/present#scene/interrupt-evidence/trace`

  The logical canvas widths must be `960`, `1080`, and `1280` respectively.
  Capture the receipt state and open-inspector state at each viewport. Confirm
  no page scroll, unchanged primary geometry, bounded raw evidence, focus
  restoration, compact chat exclusion, and a clean browser console.
  ```

  Replace checklist claims that `1024x768` scales a fixed `1280x720` canvas to
  `0.8`; that behavior is intentionally removed. Preserve the separate
  architecture-figure checks because graph visual repair is outside this slice.

- [ ] **Step 2: Run the browser at representative ratios**

  Start the existing dev server if it is not already running:

  ```powershell
  pnpm --dir web dev
  ```

  Use the available Playwright automation to capture `/present#scene/architecture/node-use/focus/node-use` and `/present#scene/interrupt-evidence/trace` at:

  ```text
  1024x768
  1200x800
  1280x720
  ```

  For each viewport, verify:

  1. `document.documentElement.scrollWidth === window.innerWidth` and `scrollHeight === window.innerHeight`;
  2. the logical canvas width is respectively `960`, `1080`, and `1280` CSS pixels before transform;
  3. the current claim, graph, progress, and evidence receipt remain present;
  4. opening the inspector does not change the primary region's width or height;
  5. raw evidence scrolls inside the inspector rather than the page;
  6. `Escape` closes the inspector and returns focus to the triggering control;
  7. at `1024x768`, any visible chat is hidden while the inspector is open;
  8. no new browser-console errors appear.

  Measure primary geometry before and after opening:

  ```js
  const primary = document.querySelector('[aria-label="primary presentation region"]');
  const before = primary?.getBoundingClientRect();
  // Click Inspect evidence, then read the same rectangle again.
  const after = primary?.getBoundingClientRect();
  ({ before: { width: before?.width, height: before?.height }, after: { width: after?.width, height: after?.height } });
  ```

  Expected: before and after dimensions are equal at each viewport. Screenshots are review artifacts; save them under an ignored temporary directory and do not commit them.

- [ ] **Step 3: Troubleshoot browser-only failures before continuing**

  Use these diagnostics rather than compensating with scene-specific CSS:

  - If `@container` rules do not fire, inspect `.presentation-canvas` and confirm computed `container-type: inline-size` and `container-name: presentation-canvas`. A component cannot query itself; the stage must be its descendant.
  - If the canvas is still letterboxed at `1024x768`, inspect the inline logical width. It must be `960px`; a remaining `PRESENTATION_WIDTH` import usually means the component still forces `1280px`.
  - If stage content is taller than the canvas, search for `100dvh` below `.presentation-canvas`. Descendants must use `height: 100%` so the logical canvas owns height.
  - If opening evidence changes graph fit, search for a remaining evidence grid column, width variable, or React Flow resize observer triggered by layout width. The inspector must be positioned over the stage.
  - If one Escape closes two layers, remove component-local Escape handling. The route's window listener is the only Escape owner.
  - If focus is lost after closing, ensure the inspector captures `document.activeElement` before focusing its close button and restores it from the effect cleanup.
  - If JSDOM tests pass but compact layout fails, do not add DOM-size mocks. Container queries and transformed geometry require the browser checks above.

- [ ] **Step 4: Commit the repeatable visual-review procedure**

  ```powershell
  git add docs/runbooks/presentation-visual-review.md
  git commit -m "docs: verify adaptive presentation geometry"
  ```

---

### Task 7: Documentation, Regression, and Plan Archival

**Files:**
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-06-adaptive-presentation-canvas.md` to `docs/historical/superpowers/plans/2026-07-06-adaptive-presentation-canvas.md`

**Interfaces:**
- Documents: adaptive `4:3` through `16:9` behavior
- Documents: evidence receipt and explicit inspector
- Preserves: console product evidence drawer wording where it describes `/console`, not `/present`

- [ ] **Step 1: Update user-facing presentation documentation**

  In `web/README.md`, replace only presentation-specific fixed-canvas and evidence-drawer language. The resulting wording must state:

  ```markdown
  The presentation keeps a 720px logical height and adapts continuously from a
  960px-wide 4:3 canvas to a 1280px-wide 16:9 canvas. More extreme viewports
  letterbox at the nearest reviewed ratio.

  Evidence beats update a compact receipt in the progress row. Raw and
  interpreted protocol evidence opens only through the centered inspector, so
  evidence never resizes the active graph or scene.
  ```

  Do not replace `/console` documentation that accurately calls its own product surface an evidence drawer.

- [ ] **Step 2: Mark the roadmap item completed**

  Change roadmap item 12 from `Then` to `Completed`, preserve the design-spec link, and add the historical implementation-plan link. Renumbering is unnecessary unless another active change has inserted a colliding item.

- [ ] **Step 3: Archive the completed plan**

  Run:

  ```powershell
  New-Item -ItemType Directory -Force docs/historical/superpowers/plans | Out-Null
  git mv docs/superpowers/plans/2026-07-06-adaptive-presentation-canvas.md docs/historical/superpowers/plans/2026-07-06-adaptive-presentation-canvas.md
  ```

  Update the roadmap link to the historical path. Search for the active path and ensure no live link remains:

  ```powershell
  rg -n -F 'superpowers/plans/2026-07-06-adaptive-presentation-canvas.md' docs web skills
  ```

  Expected: only the historical path appears where the completed implementation is cited.

- [ ] **Step 4: Run complete verification**

  Run:

  ```powershell
  pnpm --dir web test
  pnpm --dir web typecheck
  pnpm --dir web build
  git diff --check
  ```

  Expected:

  - all console, RPC, and server tests pass;
  - all package typechecks exit `0`;
  - the production build succeeds;
  - `git diff --check` reports no whitespace errors.

- [ ] **Step 5: Run React diagnostics**

  Use the repository's `react-doctor` skill or its documented local command against `web/apps/console`. Review every new finding. Fix findings caused by this slice; record unrelated pre-existing findings without broad cleanup.

- [ ] **Step 6: Review the scope boundary**

  Confirm the final diff does not modify:

  ```text
  web/apps/console/src/presentation/figures/* layout behavior
  web/apps/console/src/presentation/WorkflowGraphStage.tsx node placement
  Dagre spacing or graph dimensions
  scene-specific caption sizes to suppress overflow
  canonical evidence recording data
  ```

  If visual overflow remains inside an individual graph after the canvas and inspector work passes, report it as the next visual slice rather than hiding it with unrelated CSS here.

- [ ] **Step 7: Commit documentation and archive**

  ```powershell
  git add web/README.md docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-06-adaptive-presentation-canvas.md
  git commit -m "docs: record adaptive presentation canvas"
  ```

---

## Final Review Checklist

Before reporting completion, verify each item directly rather than relying on task-level results:

- [ ] `1024x768` uses a `960x720` logical canvas without vertical letterboxing.
- [ ] `1200x800` uses a `1080x720` logical canvas.
- [ ] `1280x720` uses a `1280x720` logical canvas.
- [ ] Ratios outside `4:3` through `16:9` letterbox at the nearest supported ratio.
- [ ] Scene and graph semantic content is identical across the three reviewed ratios.
- [ ] `node-use`, `diagnose`, and `trace` beats show a receipt but never auto-open the inspector.
- [ ] `View raw evidence` and the receipt open the same centered inspector.
- [ ] Opening the inspector leaves primary geometry unchanged.
- [ ] Interpreted evidence appears before raw request/response data.
- [ ] Equivalent CLI, request, response, status, duration, and record selection remain inspectable.
- [ ] Empty, missing-status, and non-serializable evidence do not crash the route.
- [ ] Escape closes the inspector before node spotlight or discussion and restores focus.
- [ ] Beat navigation closes the inspector and restores beat-derived receipt state.
- [ ] Compact chat is hidden while the inspector is open.
- [ ] Reduced motion preserves all information and controls.
- [ ] `EvidenceDrawer`, `peek`, and presentation-owned evidence `open` vocabulary are removed.
- [ ] No scene-specific graph visual or overflow changes entered this slice.
- [ ] Full web tests, typechecks, build, React diagnostics, and browser checks have fresh passing evidence.

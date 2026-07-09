# Presentation Lifecycle Story Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the defense presentation climax from a cramped run-only proof into a multi-scene lifecycle story covering draft, artifact, deployment, run, interrupt, resume, output, and trace.

**Architecture:** Keep the existing React presentation route and timeline replay system. Add a presentation-only lifecycle fact projection from the canonical recording, split the storyboard into more scenes, and reuse `DemoWorkflowScene` / `GuidedProductMoment` only where they still fit. New components should present lifecycle facts without mutating runtime state.

**Tech Stack:** React 19, TypeScript, Vitest, Vite, Playwright smoke scripts, existing presentation CSS, existing canonical recording at `web/apps/console/src/demo/recordings/lda-report-success.v1.json`.

## Global Constraints

- Do not invent runtime facts. Derive artifact, deployment, run, interrupt, output, and trace facts from the canonical recording where possible.
- Prepared draft context may point to `examples/lda_report_workflow`, but must be labelled as prepared authoring context, not recorded runtime evidence.
- Keep native internal scrolling for long panels. Do not allow whole-page presentation scrolling.
- Keep chat secondary on graph/evidence scenes.
- Keep live/replay truth badge visible.
- Do not change Python workflow runtime behavior.
- Every task must update or add tests before implementation.

---

## File Structure

- Modify `web/apps/console/src/presentation/storyboard.ts`: replace the current two-scene climax with four product scenes and renumber evaluation/conclusion.
- Modify `web/apps/console/src/presentation/storyboard.test.ts`: pin scene IDs, order, and key beat IDs.
- Create `web/apps/console/src/presentation/demo-lifecycle-facts.ts`: projection model for prepared draft context, artifact, deployment, bindings, and run readiness.
- Create `web/apps/console/src/presentation/DemoLifecycleScene.tsx`: scene component for prepared workflow lifecycle facts.
- Create `web/apps/console/src/presentation/DemoLifecycleScene.test.tsx`: component tests for draft/artifact/deployment/ready-run beats.
- Modify `web/apps/console/src/presentation/SceneBody.tsx`: route new `view` value to `DemoLifecycleScene`.
- Modify `web/apps/console/src/presentation/demo-beat-requirements.ts`: update replay priming for new scene IDs and beats.
- Modify `web/apps/console/src/presentation/DemoWorkflowScene.tsx`: support new Scene 10/11/12 beat IDs or delegate to focused components where clearer.
- Modify `web/apps/console/src/presentation/GuidedProductMoment.tsx`: keep only interrupt/resume/output/trace-specific moments.
- Modify `web/apps/console/src/presentation/presentation.css` and `web/apps/console/src/presentation/styles/demo-workflow.css`: add lifecycle scene layout and adjust demo scene widths.
- Modify relevant tests under `web/apps/console/src/presentation/`.
- Modify `docs/current_roadmap.md`: mark this slice complete after implementation.
- Move this plan to `docs/historical/superpowers/plans/` when complete.

---

### Task 1: Split The Storyboard Into Lifecycle Demo Scenes

**Files:**
- Modify: `web/apps/console/src/presentation/storyboard.ts`
- Modify: `web/apps/console/src/presentation/storyboard.test.ts`

**Interfaces:**
- Consumes: existing `sceneBeat(...)`, `SceneDefinition`, `findScene`, `findBeat`.
- Produces: new scene IDs `prepared-lifecycle`, `run-from-deployment`, `typed-human-boundary`, `resume-output-evidence`.

- [ ] **Step 1: Write failing storyboard tests**

Add tests to `web/apps/console/src/presentation/storyboard.test.ts`:

```ts
it("splits the demo climax into lifecycle, run, interrupt, and evidence scenes", () => {
  expect(findScene("prepared-lifecycle")?.number).toBe(9);
  expect(findScene("run-from-deployment")?.number).toBe(10);
  expect(findScene("typed-human-boundary")?.number).toBe(11);
  expect(findScene("resume-output-evidence")?.number).toBe(12);
  expect(findScene("evaluation")?.number).toBe(13);
  expect(findScene("conclusion")?.number).toBe(14);
});

it("defines the lifecycle story beats before run evidence", () => {
  expect(findBeat("prepared-lifecycle", "draft")?.caption).toMatch(/prepared authoring/i);
  expect(findBeat("prepared-lifecycle", "artifact")?.caption).toMatch(/artifact/i);
  expect(findBeat("prepared-lifecycle", "deployment")?.caption).toMatch(/source/i);
  expect(findBeat("prepared-lifecycle", "ready-run")?.caption).toMatch(/ready/i);
});

it("defines focused run, interrupt, and evidence beats", () => {
  expect(findBeat("run-from-deployment", "input")).toBeDefined();
  expect(findBeat("run-from-deployment", "operation")).toBeDefined();
  expect(findBeat("run-from-deployment", "graph")).toBeDefined();
  expect(findBeat("typed-human-boundary", "interrupt")).toBeDefined();
  expect(findBeat("typed-human-boundary", "approval")).toBeDefined();
  expect(findBeat("typed-human-boundary", "cancel")).toBeDefined();
  expect(findBeat("resume-output-evidence", "resume")).toBeDefined();
  expect(findBeat("resume-output-evidence", "output")).toBeDefined();
  expect(findBeat("resume-output-evidence", "trace")).toBeDefined();
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts
```

Expected: fails because the new scene IDs do not exist.

- [ ] **Step 3: Update storyboard scene definitions**

In `storyboard.ts`, replace current `workflow-demo` and `interrupt-evidence` scenes with:

```ts
{
  id: "prepared-lifecycle",
  number: 9,
  title: "Prepared Workflow Lifecycle",
  claimClass: "implemented",
  evidencePointer: "examples/lda_report_workflow; deployment inspect replay evidence",
  stageTheme: "night",
  view: "demo-lifecycle",
  beats: [
    sceneBeat("draft", "Prepared draft", "Prepared authoring context creates a reusable report workflow.", { chatMode: "hidden", chatTheme: "light" }),
    sceneBeat("artifact", "Saved artifact", "The workflow is preserved as a versioned artifact.", { chatMode: "hidden", chatTheme: "light" }),
    sceneBeat("deployment", "Deployment bindings", "Deployment binds workflow requirements to configured local sources.", { chatMode: "hidden", chatTheme: "light" }),
    sceneBeat("ready-run", "Ready to run", "The deployment can start a persisted run from workflow input.", { chatMode: "hidden", chatTheme: "light" }),
  ],
},
{
  id: "run-from-deployment",
  number: 10,
  title: "Run From Deployment",
  claimClass: "implemented",
  evidencePointer: "workflow.runs.start replay evidence",
  stageTheme: "night",
  view: "demo",
  beats: [
    sceneBeat("input", "Workflow input", "The run starts from selected documents and an issue board path.", { chatMode: "hidden", chatTheme: "light" }),
    sceneBeat("operation", "Start operation", "A public operation starts a durable workflow run.", { chatMode: "hidden", chatTheme: "light" }),
    sceneBeat("graph", "Reusable graph", "The run follows a reusable workflow graph, not a chat transcript.", { chatMode: "hidden", chatTheme: "light" }),
  ],
},
{
  id: "typed-human-boundary",
  number: 11,
  title: "Typed Human Boundary",
  claimClass: "implemented",
  evidencePointer: "typed interrupt payload and resume contract",
  stageTheme: "night",
  view: "demo",
  beats: [
    sceneBeat("interrupt", "Interrupt payload", "Execution reaches a declared issue-review boundary.", { chatMode: "hidden", chatTheme: "light" }),
    sceneBeat("approval", "Approval", "The operator reviews a schema-backed resume request.", { chatMode: "hidden", chatTheme: "light" }),
    sceneBeat("cancel", "Cancel path", "Replay cancellation stays honest and does not show submitted evidence.", { chatMode: "hidden", chatTheme: "light" }),
  ],
},
{
  id: "resume-output-evidence",
  number: 12,
  title: "Resume, Output, Evidence",
  claimClass: "implemented",
  evidencePointer: "workflow.runs.resume, workflow output, and trace replay evidence",
  stageTheme: "night",
  view: "demo",
  beats: [
    sceneBeat("resume", "Resume", "The submitted payload resumes the same persisted run.", { chatMode: "hidden", chatTheme: "light" }),
    sceneBeat("output", "Output", "The workflow produces the report and issue-board changes.", { chatMode: "hidden", chatTheme: "light" }),
    sceneBeat("trace", "Trace evidence", "Trace frames and protocol evidence remain inspectable.", { chatMode: "dock", chatTheme: "light", evidencePresentation: "receipt" }),
  ],
},
```

Renumber `evaluation` to `13` and `conclusion` to `14`.

Extend the `SceneDefinition["view"]` union wherever it is declared to include `"demo-lifecycle"`.

- [ ] **Step 4: Run storyboard tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/storyboard.test.ts
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts
git commit -m "feat: split presentation demo story"
```

---

### Task 2: Add Lifecycle Fact Projection

**Files:**
- Create: `web/apps/console/src/presentation/demo-lifecycle-facts.ts`
- Create: `web/apps/console/src/presentation/demo-lifecycle-facts.test.ts`

**Interfaces:**
- Consumes: `DemoTimelineController`, canonical demo events.
- Produces:

```ts
export type DemoLifecycleFacts = {
  readonly draft: { readonly label: string; readonly source: string; readonly status: string };
  readonly artifact: { readonly id: string; readonly version: number | null };
  readonly deployment: {
    readonly id: string;
    readonly driftPolicy: string;
    readonly bindings: ReadonlyArray<readonly [string, string]>;
  };
  readonly run: { readonly id: string | null; readonly status: string };
};

export const projectDemoLifecycleFacts = (demo: DemoTimelineController) => DemoLifecycleFacts;
```

- [ ] **Step 1: Write failing projection tests**

Create `demo-lifecycle-facts.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import { initialDemoTimelineState } from "../demo/timeline/reducer.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { projectDemoLifecycleFacts } from "./demo-lifecycle-facts.js";

const controller = (): DemoTimelineController => {
  const recording = loadCanonicalDemoRecording();
  return {
    state: {
      ...initialDemoTimelineState,
      mode: "replay",
      phase: "paused",
      events: recording.events,
      appliedCount: recording.events.length,
      autoplay: false,
    },
    inFlight: false,
    interruptPayload: null,
    output: null,
    trace: null,
    missingDeploymentMessage: null,
    recordingId: recording.recordingId,
    canStart: true,
    setMode: vi.fn(),
    start: vi.fn(),
    pause: vi.fn(),
    play: vi.fn(),
    next: vi.fn(async () => {}),
    submitSelectedIssues: vi.fn(async () => {}),
    cancelReview: vi.fn(async () => {}),
    restart: vi.fn(),
    primeReplayToStage: vi.fn(),
  };
};

describe("projectDemoLifecycleFacts", () => {
  it("projects prepared draft context without pretending it was runtime evidence", () => {
    const facts = projectDemoLifecycleFacts(controller());
    expect(facts.draft.label).toBe("lda report workflow");
    expect(facts.draft.source).toContain("examples/lda_report_workflow");
    expect(facts.draft.status).toBe("prepared context");
  });

  it("projects artifact and deployment facts from deployment inspect evidence", () => {
    const facts = projectDemoLifecycleFacts(controller());
    expect(facts.artifact).toEqual({ id: "lda_report_case_study", version: 1 });
    expect(facts.deployment.id).toBe("lda_report_case_study.default");
    expect(facts.deployment.driftPolicy).toBe("block");
    expect(facts.deployment.bindings).toContainEqual(["local.lda_docs", "local.lda_docs"]);
  });

  it("projects run readiness from the run start event", () => {
    const facts = projectDemoLifecycleFacts(controller());
    expect(facts.run.id).toBe("run_recorded_lda_report");
    expect(facts.run.status).toBe("interrupted");
  });
});
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/demo-lifecycle-facts.test.ts
```

Expected: fails because module does not exist.

- [ ] **Step 3: Implement projection**

Create `demo-lifecycle-facts.ts`:

```ts
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";

export type DemoLifecycleFacts = {
  readonly draft: {
    readonly label: string;
    readonly source: string;
    readonly status: string;
  };
  readonly artifact: {
    readonly id: string;
    readonly version: number | null;
  };
  readonly deployment: {
    readonly id: string;
    readonly driftPolicy: string;
    readonly bindings: ReadonlyArray<readonly [string, string]>;
  };
  readonly run: {
    readonly id: string | null;
    readonly status: string;
  };
};

const deploymentInspect = (demo: DemoTimelineController) =>
  demo.state.events.find((event) => event.stage === "deployment_check");

const runStart = (demo: DemoTimelineController) =>
  demo.state.events.find((event) => event.stage === "run_start");

const readBindings = (value: unknown): ReadonlyArray<readonly [string, string]> => {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (!Array.isArray(entry) || entry.length !== 2) return [];
    const [from, to] = entry;
    return typeof from === "string" && typeof to === "string" ? [[from, to] as const] : [];
  });
};

/**
 * Presentation-only lifecycle facts. Draft context is prepared example context;
 * artifact/deployment/run facts come from replay evidence when available.
 */
export const projectDemoLifecycleFacts = (demo: DemoTimelineController): DemoLifecycleFacts => {
  const deployment = deploymentInspect(demo);
  const deploymentInterpreted = deployment?.interpreted as
    | {
        id?: string;
        artifactId?: string;
        artifactVersion?: number;
        driftPolicy?: string;
        bindings?: unknown;
      }
    | undefined;
  const run = runStart(demo);
  const runInterpreted = run?.interpreted as
    | { runId?: string; status?: string }
    | undefined;

  return {
    draft: {
      label: "lda report workflow",
      source: "examples/lda_report_workflow",
      status: "prepared context",
    },
    artifact: {
      id: deploymentInterpreted?.artifactId ?? "unavailable",
      version: typeof deploymentInterpreted?.artifactVersion === "number"
        ? deploymentInterpreted.artifactVersion
        : null,
    },
    deployment: {
      id: deploymentInterpreted?.id ?? "unavailable",
      driftPolicy: deploymentInterpreted?.driftPolicy ?? "unavailable",
      bindings: readBindings(deploymentInterpreted?.bindings),
    },
    run: {
      id: runInterpreted?.runId ?? run?.resultingIds.runId ?? null,
      status: runInterpreted?.status ?? "not started",
    },
  };
};
```

- [ ] **Step 4: Run projection tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/demo-lifecycle-facts.test.ts
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add web/apps/console/src/presentation/demo-lifecycle-facts.ts web/apps/console/src/presentation/demo-lifecycle-facts.test.ts
git commit -m "feat: project demo lifecycle facts"
```

---

### Task 3: Render Prepared Workflow Lifecycle Scene

**Files:**
- Create: `web/apps/console/src/presentation/DemoLifecycleScene.tsx`
- Create: `web/apps/console/src/presentation/DemoLifecycleScene.test.tsx`
- Modify: `web/apps/console/src/presentation/SceneBody.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: `projectDemoLifecycleFacts(demo)`, `SceneBeatDefinition`.
- Produces: `DemoLifecycleScene` component.

- [ ] **Step 1: Write failing component tests**

Create `DemoLifecycleScene.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import { initialDemoTimelineState } from "../demo/timeline/reducer.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { DemoLifecycleScene } from "./DemoLifecycleScene.js";
import { findBeat, findScene } from "./storyboard.js";

const recording = loadCanonicalDemoRecording();
const demo: DemoTimelineController = {
  state: {
    ...initialDemoTimelineState,
    mode: "replay",
    phase: "paused",
    events: recording.events,
    appliedCount: recording.events.length,
    autoplay: false,
  },
  inFlight: false,
  interruptPayload: null,
  output: null,
  trace: null,
  missingDeploymentMessage: null,
  recordingId: recording.recordingId,
  canStart: true,
  setMode: vi.fn(),
  start: vi.fn(),
  pause: vi.fn(),
  play: vi.fn(),
  next: vi.fn(async () => {}),
  submitSelectedIssues: vi.fn(async () => {}),
  cancelReview: vi.fn(async () => {}),
  restart: vi.fn(),
  primeReplayToStage: vi.fn(),
};

const renderBeat = (beatId: "draft" | "artifact" | "deployment" | "ready-run") => {
  const scene = findScene("prepared-lifecycle");
  const beat = findBeat("prepared-lifecycle", beatId);
  if (!scene || !beat) throw new Error(`missing prepared-lifecycle/${beatId}`);
  render(<DemoLifecycleScene scene={scene} beat={beat} demo={demo} />);
};

describe("DemoLifecycleScene", () => {
  it("renders prepared draft context honestly", () => {
    renderBeat("draft");
    expect(screen.getByRole("region", { name: /prepared workflow lifecycle/i })).toHaveAttribute("data-active-lifecycle", "draft");
    expect(screen.getByText("prepared context")).toBeInTheDocument();
    expect(screen.getByText("examples/lda_report_workflow")).toBeInTheDocument();
  });

  it("renders artifact and deployment facts from replay evidence", () => {
    renderBeat("deployment");
    expect(screen.getByText("lda_report_case_study")).toBeInTheDocument();
    expect(screen.getByText("lda_report_case_study.default")).toBeInTheDocument();
    expect(screen.getByText("local.lda_docs -> local.lda_docs")).toBeInTheDocument();
  });

  it("renders run readiness without claiming output exists yet", () => {
    renderBeat("ready-run");
    expect(screen.getByText("run_recorded_lda_report")).toBeInTheDocument();
    expect(screen.getByText("interrupted")).toBeInTheDocument();
    expect(screen.queryByText(/created issues/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/DemoLifecycleScene.test.tsx
```

Expected: fails because component does not exist.

- [ ] **Step 3: Implement `DemoLifecycleScene`**

Create `DemoLifecycleScene.tsx`:

```tsx
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { projectDemoLifecycleFacts } from "./demo-lifecycle-facts.js";
import { StageCaption } from "./StageCaption.js";
import type { SceneBeatDefinition, SceneDefinition } from "./storyboard.js";

type DemoLifecycleSceneProps = {
  readonly scene: SceneDefinition;
  readonly beat: SceneBeatDefinition;
  readonly demo: DemoTimelineController;
};

const stages = [
  { id: "draft", label: "Draft", description: "Prepared authoring context" },
  { id: "artifact", label: "Artifact", description: "Immutable versioned workflow" },
  { id: "deployment", label: "Deployment", description: "Configured source bindings" },
  { id: "ready-run", label: "Run-ready", description: "Persisted run can start" },
] as const;

export const DemoLifecycleScene = ({ scene, beat, demo }: DemoLifecycleSceneProps) => {
  const facts = projectDemoLifecycleFacts(demo);

  return (
    <>
      <StageCaption eyebrow="Product lifecycle" title={scene.title}>
        <p>{beat.caption}</p>
      </StageCaption>
      <section
        className="demo-lifecycle-scene"
        aria-label="prepared workflow lifecycle"
        data-active-lifecycle={beat.id}
      >
        <ol className="demo-lifecycle-scene__rail">
          {stages.map((stage) => (
            <li key={stage.id} data-active={stage.id === beat.id ? "true" : "false"}>
              <strong>{stage.label}</strong>
              <span>{stage.description}</span>
            </li>
          ))}
        </ol>

        <article className="demo-lifecycle-scene__proof">
          <h3>{stages.find((stage) => stage.id === beat.id)?.label ?? "Lifecycle"}</h3>
          {beat.id === "draft" && (
            <dl>
              <dt>Workflow</dt><dd>{facts.draft.label}</dd>
              <dt>Status</dt><dd>{facts.draft.status}</dd>
              <dt>Source</dt><dd>{facts.draft.source}</dd>
            </dl>
          )}
          {beat.id === "artifact" && (
            <dl>
              <dt>Artifact</dt><dd>{facts.artifact.id}</dd>
              <dt>Version</dt><dd>{facts.artifact.version ?? "unavailable"}</dd>
            </dl>
          )}
          {beat.id === "deployment" && (
            <dl>
              <dt>Deployment</dt><dd>{facts.deployment.id}</dd>
              <dt>Drift policy</dt><dd>{facts.deployment.driftPolicy}</dd>
              <dt>Bindings</dt>
              <dd>
                <ul>
                  {facts.deployment.bindings.map(([from, to]) => (
                    <li key={`${from}:${to}`}>{from} -&gt; {to}</li>
                  ))}
                </ul>
              </dd>
            </dl>
          )}
          {beat.id === "ready-run" && (
            <dl>
              <dt>Run</dt><dd>{facts.run.id ?? "not started"}</dd>
              <dt>Status</dt><dd>{facts.run.status}</dd>
              <dt>Deployment</dt><dd>{facts.deployment.id}</dd>
            </dl>
          )}
        </article>
      </section>
    </>
  );
};
```

- [ ] **Step 4: Route new scene view**

In `SceneBody.tsx`, import and route:

```tsx
import { DemoLifecycleScene } from "./DemoLifecycleScene.js";
```

Add switch case:

```tsx
case "demo-lifecycle":
  return <DemoLifecycleScene scene={scene} beat={beat} demo={demo} />;
```

Update the `assertNever` union compile errors by adding `"demo-lifecycle"` to the `SceneDefinition` view union in `storyboard.ts`.

- [ ] **Step 5: Add lifecycle scene CSS**

Append to `presentation.css`:

```css
.demo-lifecycle-scene {
  display: grid;
  grid-template-columns: minmax(18rem, 0.8fr) minmax(0, 1.2fr);
  gap: 1rem;
  min-height: 0;
}

.demo-lifecycle-scene__rail {
  display: grid;
  gap: 0.65rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.demo-lifecycle-scene__rail li,
.demo-lifecycle-scene__proof {
  border: 1px solid var(--stage-line);
  border-radius: var(--presentation-panel-radius, 0.85rem);
  background: var(--stage-surface);
  color: var(--text-primary);
}

.demo-lifecycle-scene__rail li {
  padding: 0.8rem 0.9rem;
  opacity: 0.62;
}

.demo-lifecycle-scene__rail li[data-active="true"] {
  border-color: var(--accent-cyan);
  opacity: 1;
}

.demo-lifecycle-scene__rail strong,
.demo-lifecycle-scene__rail span {
  display: block;
}

.demo-lifecycle-scene__rail span {
  color: var(--text-muted);
  font-size: 0.86rem;
}

.demo-lifecycle-scene__proof {
  min-height: 0;
  overflow: auto;
  padding: 1rem 1.1rem;
  scrollbar-width: none;
}

.demo-lifecycle-scene__proof::-webkit-scrollbar {
  display: none;
}

.demo-lifecycle-scene__proof h3 {
  margin: 0 0 1rem;
  color: var(--accent-cyan);
  font: 700 1.35rem/1 var(--font-interface);
}

.demo-lifecycle-scene__proof dl {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.55rem 0.9rem;
  margin: 0;
}

.demo-lifecycle-scene__proof dt {
  color: var(--text-muted);
  font-weight: 700;
}

.demo-lifecycle-scene__proof dd {
  margin: 0;
  font-family: var(--font-mono);
}
```

- [ ] **Step 6: Run lifecycle scene tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/DemoLifecycleScene.test.tsx src/presentation/SceneBody.test.tsx
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add web/apps/console/src/presentation/DemoLifecycleScene.tsx web/apps/console/src/presentation/DemoLifecycleScene.test.tsx web/apps/console/src/presentation/SceneBody.tsx web/apps/console/src/presentation/presentation.css web/apps/console/src/presentation/storyboard.ts
git commit -m "feat: add prepared lifecycle scene"
```

---

### Task 4: Remap Demo Beat Readiness And Scene Routing

**Files:**
- Modify: `web/apps/console/src/presentation/demo-beat-requirements.ts`
- Modify: `web/apps/console/src/presentation/demo-beat-requirements.test.ts`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.tsx`
- Modify: `web/apps/console/src/presentation/DemoWorkflowScene.test.tsx`

**Interfaces:**
- Consumes: new storyboard scene IDs and beat IDs.
- Produces: correct replay priming for direct hashes.

- [ ] **Step 1: Update failing beat requirement tests**

In `demo-beat-requirements.test.ts`, replace old scene IDs with:

```ts
it.each([
  ["prepared-lifecycle", "draft", "deployment_check"],
  ["prepared-lifecycle", "artifact", "deployment_check"],
  ["prepared-lifecycle", "deployment", "deployment_check"],
  ["prepared-lifecycle", "ready-run", "run_start"],
  ["run-from-deployment", "input", "run_start"],
  ["run-from-deployment", "operation", "run_start"],
  ["run-from-deployment", "graph", "run_start"],
  ["typed-human-boundary", "interrupt", "interrupt"],
  ["typed-human-boundary", "approval", "interrupt"],
  ["typed-human-boundary", "cancel", "interrupt"],
  ["resume-output-evidence", "resume", "run_resume"],
  ["resume-output-evidence", "output", "run_resume"],
  ["resume-output-evidence", "trace", "trace_read"],
] as const)("maps %s/%s to %s", (sceneId, beatId, stage) => {
  expect(requirementForDemoBeat(sceneId, beatId).requiredStage).toBe(stage);
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/demo-beat-requirements.test.ts
```

Expected: fails until requirements mapping is updated.

- [ ] **Step 3: Update requirements mapping**

In `demo-beat-requirements.ts`, replace old keys with:

```ts
const requirements: Readonly<Record<string, DemoBeatRequirement>> = {
  "prepared-lifecycle/draft": {
    requiredStage: "deployment_check",
    reason: "Prepared draft beat needs deployment inspect evidence for lifecycle context.",
  },
  "prepared-lifecycle/artifact": {
    requiredStage: "deployment_check",
    reason: "Artifact beat needs deployment inspect evidence.",
  },
  "prepared-lifecycle/deployment": {
    requiredStage: "deployment_check",
    reason: "Deployment beat needs configured source bindings.",
  },
  "prepared-lifecycle/ready-run": {
    requiredStage: "run_start",
    reason: "Ready-run beat needs the recorded run id and status.",
  },
  "run-from-deployment/input": {
    requiredStage: "run_start",
    reason: "Input beat needs workflow input from run start.",
  },
  "run-from-deployment/operation": {
    requiredStage: "run_start",
    reason: "Operation beat needs the recorded run start.",
  },
  "run-from-deployment/graph": {
    requiredStage: "run_start",
    reason: "Graph beat needs the persisted run id.",
  },
  "typed-human-boundary/interrupt": {
    requiredStage: "interrupt",
    reason: "Interrupt beat needs the typed review payload.",
  },
  "typed-human-boundary/approval": {
    requiredStage: "interrupt",
    reason: "Approval beat needs the typed review payload before controls can act.",
  },
  "typed-human-boundary/cancel": {
    requiredStage: "interrupt",
    reason: "Cancel beat needs the review payload but no submitted replay evidence.",
  },
  "resume-output-evidence/resume": {
    requiredStage: "run_resume",
    reason: "Resume beat needs the recorded resume operation.",
  },
  "resume-output-evidence/output": {
    requiredStage: "run_resume",
    reason: "Output beat needs the resumed run output.",
  },
  "resume-output-evidence/trace": {
    requiredStage: "trace_read",
    reason: "Trace beat needs the recorded trace read.",
  },
};
```

- [ ] **Step 4: Update demo scene routing**

In `DemoWorkflowScene.tsx`, adapt helper functions:

```ts
const layoutForBeat = (beatId: string): DemoWorkflowLayout => {
  if (beatId === "operation" || beatId === "resume") return "operation";
  if (beatId === "interrupt") return "interrupt";
  if (beatId === "approval" || beatId === "cancel") return "approval";
  if (beatId === "trace" || beatId === "output") return "evidence";
  return "graph";
};

const operationStageByBeat: Readonly<Record<string, DemoEvent["stage"] | undefined>> = {
  operation: "run_start",
  resume: "run_resume",
  trace: "trace_read",
};
```

Make `isGuidedScene10` become a set-based check:

```ts
const isGuidedDemoMoment = scene.id === "typed-human-boundary"
  || scene.id === "resume-output-evidence";
```

For `run-from-deployment/input`, render a new input-focused branch in `DemoWorkflowScene` or delegate it to `GuidedProductMoment` if Task 5 handles it. The simplest first pass is to treat `input` as a graph scene with `RunInputFacts` in the expanded operation area.

- [ ] **Step 5: Update tests**

In `DemoWorkflowScene.test.tsx`, replace old route assertions:

```ts
renderBeat("approval", "typed-human-boundary");
renderBeat("resume", "resume-output-evidence");
renderBeat("output", "resume-output-evidence");
renderBeat("trace", "resume-output-evidence");
```

Keep assertions that approval has `data-demo-layout="approval"` and no `Output not created yet`.

- [ ] **Step 6: Run demo tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/demo-beat-requirements.test.ts src/presentation/DemoWorkflowScene.test.tsx src/presentation/PresentationRoute.test.tsx
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add web/apps/console/src/presentation/demo-beat-requirements.ts web/apps/console/src/presentation/demo-beat-requirements.test.ts web/apps/console/src/presentation/DemoWorkflowScene.tsx web/apps/console/src/presentation/DemoWorkflowScene.test.tsx web/apps/console/src/presentation/PresentationRoute.test.tsx
git commit -m "feat: remap demo replay beats"
```

---

### Task 5: Polish Factual Panels For Scroll And Hierarchy

**Files:**
- Modify: `web/apps/console/src/presentation/RunFactsPanel.tsx`
- Modify: `web/apps/console/src/presentation/RunFactsPanel.test.tsx`
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.tsx`
- Modify: `web/apps/console/src/presentation/GuidedProductMoment.test.tsx`
- Modify: `web/apps/console/src/presentation/presentation.css`

**Interfaces:**
- Consumes: `DemoRunFacts`.
- Produces: scroll-contained factual panels for approval/resume/output/trace.

- [ ] **Step 1: Add tests for no wasted approval output and visible report**

In `GuidedProductMoment.test.tsx`, add:

```tsx
it("keeps approval focused on input and decision without pre-resume output", () => {
  render(
    <GuidedProductMoment
      beat={findBeat("typed-human-boundary", "approval")!}
      demo={demo}
      contract={contract}
      operation={null}
      approvalActions={{
        state: "ready",
        canSubmit: true,
        canCancel: true,
        submit: vi.fn(async () => {}),
        cancel: vi.fn(async () => {}),
      }}
      openEvidence={vi.fn()}
    />,
  );

  expect(screen.getByText("Workflow input")).toBeInTheDocument();
  expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
  expect(screen.queryByText("Output not created yet")).not.toBeInTheDocument();
  expect(screen.getByText(/lda.chat Thesis And Project Readiness Report/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Ensure output markdown has a labelled scroll region**

In `RunFactsPanel.tsx`, wrap markdown preview:

```tsx
<div className="run-facts-markdown-region" role="region" aria-label="workflow markdown output">
  <pre className="run-facts-markdown-preview">{facts.output.markdownPreview}</pre>
</div>
```

Update `RunFactsPanel.test.tsx`:

```tsx
expect(screen.getByRole("region", { name: /workflow markdown output/i })).toBeInTheDocument();
```

- [ ] **Step 3: Keep approval output removed**

In `GuidedProductMoment.tsx`, ensure approval branch renders only:

```tsx
<div className="guided-product-moment__approval-grid">
  <RunInputFacts facts={facts} />
  <InterruptDecisionForm ... />
</div>
```

- [ ] **Step 4: Add scroll containment CSS**

In `presentation.css`, keep or add:

```css
.guided-product-moment__primary,
.guided-product-moment__approval-grid,
.guided-product-moment__resume-grid {
  min-height: 0;
  overflow: hidden;
}

.guided-product-moment[data-moment="approval"] .run-facts-card,
.guided-product-moment[data-moment="approval"] .interrupt-decision-form,
.guided-product-moment[data-moment="resume"] .run-facts-card,
.guided-product-moment[data-moment="output"] .run-facts-card,
.run-facts-markdown-region {
  min-height: 0;
  overflow: auto;
  scrollbar-width: none;
}

.guided-product-moment[data-moment="approval"] .run-facts-card::-webkit-scrollbar,
.guided-product-moment[data-moment="approval"] .interrupt-decision-form::-webkit-scrollbar,
.guided-product-moment[data-moment="resume"] .run-facts-card::-webkit-scrollbar,
.guided-product-moment[data-moment="output"] .run-facts-card::-webkit-scrollbar,
.run-facts-markdown-region::-webkit-scrollbar {
  display: none;
}
```

- [ ] **Step 5: Run panel tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation/RunFactsPanel.test.tsx src/presentation/GuidedProductMoment.test.tsx
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add web/apps/console/src/presentation/RunFactsPanel.tsx web/apps/console/src/presentation/RunFactsPanel.test.tsx web/apps/console/src/presentation/GuidedProductMoment.tsx web/apps/console/src/presentation/GuidedProductMoment.test.tsx web/apps/console/src/presentation/presentation.css
git commit -m "fix: clarify demo factual panels"
```

---

### Task 6: Visual Smoke And Roadmap Completion

**Files:**
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-09-presentation-lifecycle-story-expansion.md` to `docs/historical/superpowers/plans/2026-07-09-presentation-lifecycle-story-expansion.md`

**Interfaces:**
- Consumes: completed code from Tasks 1-5.
- Produces: verification evidence and roadmap state.

- [ ] **Step 1: Run focused presentation tests**

Run:

```bash
pnpm --dir web --filter @lda/console test -- src/presentation
```

Expected: all presentation tests pass.

- [ ] **Step 2: Run typecheck and build**

Run:

```bash
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected: typecheck clean, build succeeds. Existing Vite chunk-size warning is acceptable.

- [ ] **Step 3: Browser smoke exact routes**

With `pnpm dev` running, use Playwright or manual browser screenshots at 1280x720:

```text
http://127.0.0.1:5173/present#scene/prepared-lifecycle/draft
http://127.0.0.1:5173/present#scene/prepared-lifecycle/deployment
http://127.0.0.1:5173/present#scene/run-from-deployment/input
http://127.0.0.1:5173/present#scene/run-from-deployment/graph
http://127.0.0.1:5173/present#scene/typed-human-boundary/approval
http://127.0.0.1:5173/present#scene/resume-output-evidence/output
http://127.0.0.1:5173/present#scene/resume-output-evidence/trace
```

Expected:

- Lifecycle scene shows draft/artifact/deployment/run-ready before run detail.
- Approval has no "Output not created yet" pane.
- Output and trace panels can scroll internally.
- The page itself does not scroll.
- Live/replay truth badge remains visible.

- [ ] **Step 4: Update roadmap**

In `docs/current_roadmap.md`, mark this item completed under the active initiative:

```md
21. Completed: presentation lifecycle story expansion splits the demo climax
    into prepared lifecycle, run start, typed human boundary, and
    resume/output/evidence scenes so Draft -> Artifact -> Deployment -> Run is
    visible before the run inspector details. Design:
    [`presentation lifecycle story expansion`](superpowers/specs/2026-07-09-presentation-lifecycle-story-expansion-design.md).
    Implementation:
    [`presentation lifecycle story expansion plan`](historical/superpowers/plans/2026-07-09-presentation-lifecycle-story-expansion.md).
```

Renumber following future items.

- [ ] **Step 5: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-07-09-presentation-lifecycle-story-expansion.md docs/historical/superpowers/plans/2026-07-09-presentation-lifecycle-story-expansion.md
```

- [ ] **Step 6: Commit docs**

```bash
git add docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-09-presentation-lifecycle-story-expansion.md
git commit -m "docs: complete presentation lifecycle story expansion"
```

---

## Self-Review

- Spec coverage: The plan covers more scenes, lifecycle context before run evidence, scroll-contained factual panels, honest replay/live boundaries, and route-level smoke.
- Placeholder scan: No TBD/TODO placeholders are present.
- Type consistency: New scene IDs are consistent across storyboard, beat requirements, route examples, and tests.
- Scope note: This plan does not replace chat with a full assistant UI. It only keeps chat secondary and leaves the future AI SDK/chat component slice separate.


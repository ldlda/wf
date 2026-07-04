# Defense Storyboard Compositor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat eight-beat `/present` prototype with the approved 12-scene, multi-beat defense compositor, including stable stage regions, discussion branches, act themes, a chat dock, and 720p no-scroll navigation.

**Architecture:** A typed storyboard catalog owns scene and beat metadata. Pure navigation helpers and a reducer own semantic location, overlays, and presenter overrides; React components derive layout from that state. Existing replay, agent, graph, operation, approval, and evidence components remain the product data sources and are recomposed rather than duplicated.

**Tech Stack:** React 19, TypeScript 6, Vitest, Testing Library, Motion, existing CSS, existing replay and constrained-agent controllers. No new Effect service, transport, component library, AI SDK runtime, or RPC method is introduced in this slice.

## Global Constraints

- Preserve `/console` as the independent operator product surface.
- The main `/present` path contains exactly 12 scenes and uses `scene + beat` navigation.
- Main-path rendering must fit `1280x720` at 100% browser zoom without document scrolling.
- Stage themes change by act: paper for scenes 1-3, night for scenes 4-10, paper for scenes 11-12.
- Chat and stage themes remain independent; chat modes are `hidden`, `full`, `rail`, and `dock`.
- Discussion branches are outside the main timer and return to their originating scene and beat.
- Replay remains the default and must work without an RPC server.
- Existing agent approval, replay evidence, workflow graph, and operation events remain functional.
- Do not add compatibility behavior for the unused flat beat hashes or unused `setBeat` presentation action.
- Do not add Vercel AI Elements, Tailwind, a live LLM driver, remote phone control, or final visual polish in this plan.
- Do not use `any`, unsafe assertions, or React components stored in storyboard data.

---

### Task 1: Add the typed storyboard catalog

**Files:**
- Create: `web/apps/console/src/presentation/storyboard.ts`
- Create: `web/apps/console/src/presentation/storyboard.test.ts`
- Keep temporarily: `web/apps/console/src/presentation/beats.ts`

**Interfaces:**
- Produces: `mainScenes`, `discussionBranches`, `defaultMainLocation`, `findScene`, `findBeat`, `findDiscussionBranch`, `mainLocation`, and the `MainSceneId`, `MainLocation`, `PresentationLocation`, `SceneDefinition`, and `DiscussionBranchDefinition` types.
- Consumes: no runtime controller; this module is pure presentation metadata.

- [ ] **Step 1: Write the failing catalog tests**

```ts
import { describe, expect, it } from "vitest";
import {
  defaultMainLocation,
  discussionBranches,
  findBeat,
  findScene,
  mainScenes,
} from "./storyboard.js";

describe("defense storyboard catalog", () => {
  it("defines twelve ordered main scenes with unique scene and beat ids", () => {
    expect(mainScenes).toHaveLength(12);
    expect(mainScenes.map((scene) => scene.id)).toEqual([
      "thesis",
      "problem",
      "positioning",
      "planner-runtime",
      "lifecycle",
      "architecture",
      "authoring",
      "agent-handoff",
      "workflow-demo",
      "interrupt-evidence",
      "evaluation",
      "conclusion",
    ]);
    for (const scene of mainScenes) {
      expect(scene.beats.length).toBeGreaterThan(0);
      expect(new Set(scene.beats.map((beat) => beat.id)).size).toBe(scene.beats.length);
      expect(scene.claimClass.length).toBeGreaterThan(0);
      expect(scene.evidencePointer.length).toBeGreaterThan(0);
    }
  });

  it("uses act-level stage themes and independent chat composition", () => {
    expect(mainScenes.slice(0, 3).every((scene) => scene.stageTheme === "paper")).toBe(true);
    expect(mainScenes.slice(3, 10).every((scene) => scene.stageTheme === "night")).toBe(true);
    expect(mainScenes.slice(10).every((scene) => scene.stageTheme === "paper")).toBe(true);
    expect(findBeat("agent-handoff", "request")?.chatMode).toBe("full");
    expect(findBeat("workflow-demo", "graph")?.chatMode).toBe("rail");
    expect(findBeat("interrupt-evidence", "trace")?.chatMode).toBe("dock");
  });

  it("defines the five positioning discussion branches", () => {
    expect(discussionBranches.map((branch) => branch.id)).toEqual([
      "direct-orchestration",
      "generated-scripts",
      "hosted-automation",
      "durable-agent-graphs",
      "mcp-agent-scale",
    ]);
    expect(discussionBranches.every((branch) => branch.parentSceneId === "positioning")).toBe(true);
  });

  it("exposes a valid default location", () => {
    expect(defaultMainLocation).toEqual({ kind: "main", sceneId: "thesis", beatId: "title" });
    expect(findScene(defaultMainLocation.sceneId)?.number).toBe(1);
  });
});
```

- [ ] **Step 2: Run the catalog tests and verify the module is missing**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/storyboard.test.ts
```

Expected: FAIL because `storyboard.ts` does not exist.

- [ ] **Step 3: Implement the catalog types and definition helper**

```ts
export type ClaimClass = "motivation" | "implemented" | "evaluated" | "external-context" | "future-work";
export type StageTheme = "paper" | "night";
export type ChatTheme = "light" | "dark";
export type ChatMode = "hidden" | "full" | "rail" | "dock";
export type EvidenceMode = "hidden" | "peek" | "open";
export type SceneView =
  | "narrative"
  | "positioning"
  | "boundary"
  | "lifecycle"
  | "architecture"
  | "authoring"
  | "agent"
  | "demo"
  | "evaluation"
  | "conclusion";

export type SceneBeatDefinition = {
  readonly id: string;
  readonly title: string;
  readonly caption: string;
  readonly chatMode: ChatMode;
  readonly chatTheme: ChatTheme;
  readonly evidenceMode: EvidenceMode;
};

export type SceneDefinition = {
  readonly id: string;
  readonly number: number;
  readonly title: string;
  readonly claimClass: ClaimClass;
  readonly evidencePointer: string;
  readonly stageTheme: StageTheme;
  readonly view: SceneView;
  readonly beats: readonly SceneBeatDefinition[];
};

const defineScenes = <const Scenes extends readonly SceneDefinition[]>(scenes: Scenes): Scenes => scenes;

const sceneBeat = (
  id: string,
  title: string,
  caption: string,
  options: Partial<Pick<SceneBeatDefinition, "chatMode" | "chatTheme" | "evidenceMode">> = {},
): SceneBeatDefinition => ({
  id,
  title,
  caption,
  chatMode: options.chatMode ?? "hidden",
  chatTheme: options.chatTheme ?? "dark",
  evidenceMode: options.evidenceMode ?? "hidden",
});

export const mainScenes = defineScenes([
  {
    id: "thesis",
    number: 1,
    title: "Thesis",
    claimClass: "implemented",
    evidencePointer: "Thesis Abstract and Introduction",
    stageTheme: "paper",
    view: "narrative",
    beats: [
      sceneBeat("title", "Design and Implementation of lda.chat", "The project began as a pursuit of an AI agent for workspace automation."),
      sceneBeat("substrate", "The substrate an agent needs", "The submitted contribution creates, validates, runs, and inspects reusable workflows."),
    ],
  },
  {
    id: "problem",
    number: 2,
    title: "The Problem",
    claimClass: "motivation",
    evidencePointer: "Thesis Problem Statement and Requirements",
    stageTheme: "paper",
    view: "narrative",
    beats: [
      sceneBeat("direct-actions", "Direct actions are not reusable automation", "A tool loop can act without owning durable lifecycle records."),
      sceneBeat("missing-contracts", "The missing contracts", "Reusable automation needs schemas, bindings, persistence, traces, and recovery boundaries."),
    ],
  },
  {
    id: "positioning",
    number: 3,
    title: "Positioning and Related Systems",
    claimClass: "motivation",
    evidencePointer: "Thesis Positioning and Related Systems",
    stageTheme: "paper",
    view: "positioning",
    beats: [
      sceneBeat("landscape", "Different centers of gravity", "Tool loops, scripts, hosted automation, agent graphs, and MCP solve different parts of the problem."),
      sceneBeat("lda-position", "lda.chat's position", "Typed lifecycle contracts and provider-neutral sources are exposed for external-agent operation."),
    ],
  },
  {
    id: "planner-runtime",
    number: 4,
    title: "Planner and Runtime",
    claimClass: "implemented",
    evidencePointer: "Thesis Architecture Overview",
    stageTheme: "night",
    view: "boundary",
    beats: [
      sceneBeat("planner", "External planner", "The planner proposes and revises workflow structure."),
      sceneBeat("runtime", "Deterministic runtime", "The runtime validates, executes, records, and resumes."),
      sceneBeat("boundary", "Explicit operations", "Typed CLI and JSON-RPC operations cross the boundary."),
    ],
  },
  {
    id: "lifecycle",
    number: 5,
    title: "Workflow Lifecycle",
    claimClass: "implemented",
    evidencePointer: "Thesis Workflow Lifecycle",
    stageTheme: "night",
    view: "lifecycle",
    beats: [
      sceneBeat("draft", "Draft", "Mutable iterative authoring state."),
      sceneBeat("artifact", "Artifact", "Immutable saved workflow definition."),
      sceneBeat("deployment", "Deployment", "Logical requirements bound to concrete sources."),
      sceneBeat("run", "Run", "Persisted execution, output, status, and trace."),
    ],
  },
  {
    id: "architecture",
    number: 6,
    title: "Architecture Zoom",
    claimClass: "implemented",
    evidencePointer: "Thesis System Architecture; docs/project_map.md; docs/source_architecture.md",
    stageTheme: "night",
    view: "architecture",
    beats: [
      sceneBeat("client", "Client operations", "Human and agent clients use the same public lifecycle surface."),
      sceneBeat("api", "Transport and API", "JSON-RPC reaches WorkflowApi without owning domain behavior."),
      sceneBeat("runtime", "Runtime and providers", "The runtime resolves provider-neutral capabilities and stores lifecycle records."),
      sceneBeat("node-use", "NodeUse", "One callable node validates input, invokes a capability, and reduces output into state.", { evidenceMode: "peek" }),
    ],
  },
  {
    id: "authoring",
    number: 7,
    title: "Author, Validate, Repair",
    claimClass: "implemented",
    evidencePointer: "CLI documentation; draft authoring API; challenge UX findings",
    stageTheme: "night",
    view: "authoring",
    beats: [
      sceneBeat("discover", "Discover", "Inspect capabilities and schemas before authoring."),
      sceneBeat("author", "Author", "Focused operations build and connect the draft."),
      sceneBeat("diagnose", "Diagnose", "Structured diagnostics identify invalid state.", { evidenceMode: "peek" }),
      sceneBeat("repair", "Repair", "Repair hints lead to a valid compiled workflow."),
    ],
  },
  {
    id: "agent-handoff",
    number: 8,
    title: "Agent Handoff",
    claimClass: "implemented",
    evidencePointer: "Constrained demo agent and prepared replay recipe",
    stageTheme: "night",
    view: "agent",
    beats: [
      sceneBeat("request", "Operator request", "A thin agent interface receives the report request.", { chatMode: "full", chatTheme: "light" }),
      sceneBeat("handoff", "Prepared operation", "The interface delegates durable work to lda.chat.", { chatMode: "full", chatTheme: "light" }),
    ],
  },
  {
    id: "workflow-demo",
    number: 9,
    title: "Workflow Takes the Stage",
    claimClass: "implemented",
    evidencePointer: "Prepared replay and examples/lda_report_workflow",
    stageTheme: "night",
    view: "demo",
    beats: [
      sceneBeat("operation", "Start operation", "Raw and interpreted operation evidence enters from chat.", { chatMode: "full", chatTheme: "light" }),
      sceneBeat("graph", "Reusable graph", "The graph becomes primary while chat moves to a rail.", { chatMode: "rail", chatTheme: "light" }),
      sceneBeat("interrupt", "Typed interrupt", "Execution reaches the issue-review boundary.", { chatMode: "rail", chatTheme: "light" }),
    ],
  },
  {
    id: "interrupt-evidence",
    number: 10,
    title: "Interrupt, Resume, Evidence",
    claimClass: "implemented",
    evidencePointer: "Typed interrupt schemas, run inspection, and trace events",
    stageTheme: "night",
    view: "demo",
    beats: [
      sceneBeat("approval", "Approval", "The operator reviews a schema-backed resume request.", { chatMode: "rail", chatTheme: "light" }),
      sceneBeat("resume", "Resume", "The approved payload resumes the same persisted run.", { chatMode: "rail", chatTheme: "light" }),
      sceneBeat("output", "Output", "The workflow produces the report and issue-board changes.", { chatMode: "dock", chatTheme: "light" }),
      sceneBeat("trace", "Evidence", "Trace frames and protocol evidence remain inspectable.", { chatMode: "dock", chatTheme: "light", evidenceMode: "open" }),
    ],
  },
  {
    id: "evaluation",
    number: 11,
    title: "Evaluation",
    claimClass: "evaluated",
    evidencePointer: "Thesis Evaluation and Appendix C",
    stageTheme: "paper",
    view: "evaluation",
    beats: [
      sceneBeat("cohort", "36-trial cohort", "Two challenges, two hosted models, three profiles, and three waves."),
      sceneBeat("validity", "Bounded validity", "Manual audit separates task completion from valid product-surface evidence."),
      sceneBeat("findings", "Longitudinal findings", "Trials exposed concrete authoring and diagnostic UX gaps."),
    ],
  },
  {
    id: "conclusion",
    number: 12,
    title: "Limits and Conclusion",
    claimClass: "future-work",
    evidencePointer: "Thesis Limitations, Future Work, and Conclusion",
    stageTheme: "paper",
    view: "conclusion",
    beats: [
      sceneBeat("limits", "Implemented boundary", "The prototype is not a production sandbox, scheduler, or broad agent benchmark."),
      sceneBeat("future", "Surrounding layers", "A live LLM interface, scheduling, and broader evaluation remain future work."),
      sceneBeat("conclusion", "Planner proposes; runtime executes", "The typed substrate makes reusable agent-operated automation inspectable.", { chatMode: "dock", chatTheme: "light" }),
    ],
  },
]);

export type MainSceneId = (typeof mainScenes)[number]["id"];

export type MainLocation = {
  readonly kind: "main";
  readonly sceneId: MainSceneId;
  readonly beatId: string;
};

export type DiscussionBranchDefinition = {
  readonly id: string;
  readonly parentSceneId: MainSceneId;
  readonly title: string;
  readonly claimClass: ClaimClass;
  readonly evidencePointer: string;
  readonly summary: string;
};

```

Add these exact discussion branches with summaries grounded in the design spec:

```ts
const defineDiscussionBranches = <const Branches extends readonly DiscussionBranchDefinition[]>(
  branches: Branches,
): Branches => branches;

export const discussionBranches = defineDiscussionBranches([
  {
    id: "direct-orchestration",
    parentSceneId: "positioning",
    title: "Direct orchestration",
    claimClass: "motivation",
    evidencePointer: "Thesis: Direct LLM Tool Orchestration",
    summary: "Dynamic adaptation versus durable reusable procedure.",
  },
  {
    id: "generated-scripts",
    parentSceneId: "positioning",
    title: "Generated scripts",
    claimClass: "motivation",
    evidencePointer: "Thesis: Generated Scripts",
    summary: "Simplicity and debuggability versus managed lifecycle records.",
  },
  {
    id: "hosted-automation",
    parentSceneId: "positioning",
    title: "Hosted automation",
    claimClass: "future-work",
    evidencePointer: "Thesis: Workflow Automation Platforms and Future Work",
    summary: "Hosted triggers and scheduling are mature elsewhere and remain future work here.",
  },
  {
    id: "durable-agent-graphs",
    parentSceneId: "positioning",
    title: "Durable agent graphs",
    claimClass: "motivation",
    evidencePointer: "Thesis: Agent Graph Frameworks",
    summary: "Shared durability concerns, with a different lifecycle and source-binding emphasis.",
  },
  {
    id: "mcp-agent-scale",
    parentSceneId: "positioning",
    title: "MCP and agent-facing scale",
    claimClass: "external-context",
    evidencePointer: "Thesis: Model Context Protocol; Cloudflare Code Mode; Anthropic code execution with MCP",
    summary: "MCP is a capability protocol; progressive discovery addresses large agent-facing surfaces.",
  },
]);

export type DiscussionBranchId = (typeof discussionBranches)[number]["id"];

export type DiscussionLocation = {
  readonly kind: "discussion";
  readonly branchId: DiscussionBranchId;
};

export type PresentationLocation = MainLocation | DiscussionLocation;
```

Implement `findScene`, `findBeat`, `findDiscussionBranch`, and `mainLocation` with `Array.find` and validation. `mainLocation(sceneId, beatId)` returns `null` when either id is unknown; do not coerce invalid values.

- [ ] **Step 4: Run the catalog tests**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/storyboard.test.ts
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit the catalog**

```powershell
git add web/apps/console/src/presentation/storyboard.ts web/apps/console/src/presentation/storyboard.test.ts
git commit -m "feat: define defense storyboard catalog"
```

---

### Task 2: Replace flat beat navigation with scene and beat locations

**Files:**
- Create: `web/apps/console/src/presentation/storyboard-navigation.ts`
- Create: `web/apps/console/src/presentation/storyboard-navigation.test.ts`
- Modify: `web/apps/console/src/presentation/presentation-state.ts`
- Modify: `web/apps/console/src/presentation/presentation-state.test.ts`
- Delete after migration: `web/apps/console/src/presentation/beats.ts`
- Delete after migration: `web/apps/console/src/presentation/beats.test.ts`

**Interfaces:**
- Consumes: storyboard catalog from Task 1.
- Produces: `locationFromHash`, `hashForLocation`, `nextMainLocation`, `previousMainLocation`, `compositionForState`, and the migrated `PresentationState` / `PresentationAction` reducer contract.

- [ ] **Step 1: Write failing navigation tests**

```ts
import { describe, expect, it } from "vitest";
import {
  hashForLocation,
  locationFromHash,
  nextMainLocation,
  previousMainLocation,
} from "./storyboard-navigation.js";
import { defaultMainLocation, type MainLocation } from "./storyboard.js";

describe("storyboard navigation", () => {
  it("round-trips main and discussion hashes", () => {
    const main: MainLocation = { kind: "main", sceneId: "lifecycle", beatId: "deployment" };
    expect(locationFromHash(hashForLocation(main))).toEqual(main);
    expect(locationFromHash("#discuss/hosted-automation")).toEqual({
      kind: "discussion",
      branchId: "hosted-automation",
    });
  });

  it("falls back for unknown scene, beat, and branch hashes", () => {
    expect(locationFromHash("#scene/missing/nope")).toEqual(defaultMainLocation);
    expect(locationFromHash("#scene/lifecycle/nope")).toEqual(defaultMainLocation);
    expect(locationFromHash("#discuss/nope")).toEqual(defaultMainLocation);
  });

  it("advances within a scene before advancing to the next scene", () => {
    expect(nextMainLocation({ kind: "main", sceneId: "thesis", beatId: "title" })).toEqual({
      kind: "main",
      sceneId: "thesis",
      beatId: "substrate",
    });
    expect(nextMainLocation({ kind: "main", sceneId: "thesis", beatId: "substrate" })).toEqual({
      kind: "main",
      sceneId: "problem",
      beatId: "direct-actions",
    });
  });

  it("rewinds across scene boundaries", () => {
    expect(previousMainLocation({ kind: "main", sceneId: "problem", beatId: "direct-actions" })).toEqual({
      kind: "main",
      sceneId: "thesis",
      beatId: "substrate",
    });
  });
});
```

- [ ] **Step 2: Run navigation tests and verify failure**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/storyboard-navigation.test.ts
```

Expected: FAIL because the navigation module does not exist.

- [ ] **Step 3: Implement validated hash and sequential navigation**

Use canonical hashes only:

```text
#scene/<scene-id>/<beat-id>
#discuss/<branch-id>
```

Implement parsing with `decodeURIComponent`, catalog lookup, and `defaultMainLocation` fallback. `nextMainLocation` and `previousMainLocation` flatten `mainScenes` into ordered locations internally; they clamp at the first and last main beat.

```ts
export const hashForLocation = (location: PresentationLocation): string =>
  location.kind === "main"
    ? `#scene/${encodeURIComponent(location.sceneId)}/${encodeURIComponent(location.beatId)}`
    : `#discuss/${encodeURIComponent(location.branchId)}`;
```

- [ ] **Step 4: Write failing reducer tests for main navigation and discussion return**

```ts
it("opens a discussion branch and returns to the originating beat", () => {
  const positioned = presentationReducer(initialPresentationState, {
    type: "jump",
    location: { kind: "main", sceneId: "positioning", beatId: "lda-position" },
  });
  const opened = presentationReducer(positioned, {
    type: "open_discussion",
    branchId: "hosted-automation",
  });
  const closed = presentationReducer(opened, { type: "close_discussion" });

  expect(opened.location).toEqual({ kind: "discussion", branchId: "hosted-automation" });
  expect(closed.location).toEqual(positioned.location);
});

it("derives act and chat composition from the current beat", () => {
  const state = presentationReducer(initialPresentationState, {
    type: "jump",
    location: { kind: "main", sceneId: "workflow-demo", beatId: "graph" },
  });
  expect(compositionForState(state)).toMatchObject({
    stageTheme: "night",
    chatTheme: "light",
    chatMode: "rail",
  });
});
```

- [ ] **Step 5: Migrate the reducer**

Use this state shape:

```ts
export type PresentationState = {
  readonly location: PresentationLocation;
  readonly discussionReturn: MainLocation | null;
  readonly selectedNodeId: string | null;
  readonly evidenceModeOverride: EvidenceMode | null;
  readonly playbackMode: "replay" | "live";
  readonly stageThemeOverride: StageTheme | null;
  readonly chatThemeOverride: ChatTheme | null;
  readonly chatModeOverride: ChatMode | null;
  readonly controlsOpen: boolean;
};
```

Actions must include `next`, `previous`, `jump`, `jump_hash`, `open_discussion`, `close_discussion`, overlay actions, playback mode, theme/chat overrides, and `toggle_controls`. `compositionForState` derives catalog defaults and applies overrides; discussion branches inherit their parent scene composition.

`close_overlay` order is node spotlight, evidence, discussion, presenter controls. `next` and `previous` do nothing while a discussion branch is open.

- [ ] **Step 6: Remove the old beat module and run state/navigation tests**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/storyboard.test.ts src/presentation/storyboard-navigation.test.ts src/presentation/presentation-state.test.ts
```

Expected: all storyboard and reducer tests PASS.

- [ ] **Step 7: Commit semantic navigation**

```powershell
git add web/apps/console/src/presentation
git commit -m "refactor: navigate presentation by scene and beat"
```

---

### Task 3: Recompose the stage around stable regions

**Files:**
- Create: `web/apps/console/src/presentation/SceneBody.tsx`
- Create: `web/apps/console/src/presentation/SceneBody.test.tsx`
- Create: `web/apps/console/src/presentation/SceneRail.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`
- Delete: `web/apps/console/src/presentation/BeatRail.tsx`

**Interfaces:**
- Consumes: `PresentationState`, `compositionForState`, storyboard catalog, existing demo controller, evidence, graph, operation, and chat components.
- Produces: stable `chat`, `primary`, and `evidence` stage regions plus scene-aware rendering.

- [ ] **Step 1: Write failing SceneBody tests**

```tsx
it("renders narrative metadata without mounting the demo graph", () => {
  render(<SceneBody location={{ kind: "main", sceneId: "positioning", beatId: "landscape" }} {...fixtures} />);
  expect(screen.getByRole("heading", { name: /positioning and related systems/i })).toBeInTheDocument();
  expect(screen.queryByLabelText(/workflow graph/i)).not.toBeInTheDocument();
});

it("renders the real workflow graph for demo scenes", () => {
  render(<SceneBody location={{ kind: "main", sceneId: "workflow-demo", beatId: "graph" }} {...fixtures} />);
  expect(screen.getByLabelText(/workflow graph/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/SceneBody.test.tsx
```

Expected: FAIL because `SceneBody` does not exist.

- [ ] **Step 3: Implement scene-aware primary rendering**

`SceneBody` must not store components in the catalog. Use `scene.view` in an exhaustive switch:

```tsx
switch (scene.view) {
  case "narrative":
  case "positioning":
  case "boundary":
  case "lifecycle":
  case "architecture":
  case "authoring":
  case "evaluation":
  case "conclusion":
    return <NarrativeScene scene={scene} beat={beat} />;
  case "agent":
    return <AgentHandoffScene scene={scene} beat={beat} />;
  case "demo":
    return <DemoWorkflowScene scene={scene} beat={beat} demo={demo} selectedNodeId={selectedNodeId} selectNode={selectNode} />;
  default:
    return assertNever(scene.view);
}
```

Keep the first implementation structurally honest: narrative scenes render their claim class, title, current beat title/caption, and evidence pointer; demo scenes reuse `OperationBlock`, `WorkflowGraphStage`, and `NodeSpotlight`. Map operation events by semantic beat:

```ts
const operationStageByBeat: Readonly<Record<string, DemoEventStage | undefined>> = {
  operation: "run_start",
  interrupt: "interrupt",
  approval: "interrupt",
  resume: "run_resume",
  trace: "trace_read",
};
```

- [ ] **Step 4: Replace BeatRail with SceneRail**

`SceneRail` displays 12 compact numbered scene buttons and an internal beat progress indicator for the active scene. Its public interface is:

```ts
type SceneRailProps = {
  readonly location: PresentationLocation;
  readonly jump: (location: MainLocation) => void;
};
```

Clicking a scene jumps to its first beat. The current scene uses `aria-current="step"`; a discussion location keeps its parent scene highlighted.

- [ ] **Step 5: Rebuild PresentationStage as three stable regions**

Render this semantic structure:

```tsx
<div
  className="presentation-stage"
  data-stage-theme={composition.stageTheme}
  data-chat-theme={composition.chatTheme}
  data-chat-mode={composition.chatMode}
>
  <aside className="presentation-stage__chat">...</aside>
  <section className="presentation-stage__primary">...</section>
  <aside className="presentation-stage__evidence">...</aside>
  <SceneRail ... />
</div>
```

The route continues to own replay, prepared-agent, hash, keyboard, and evidence projection controllers. Replace old `BeatId` props with `PresentationLocation` props and update hash synchronization to use `hashForLocation`.

Decouple `OperatorChat` from the full reducer state while migrating it:

```ts
type OperatorChatProps = {
  readonly mode: ChatMode;
  readonly playbackMode: "replay" | "live";
  readonly messages?: ReadonlyArray<AgentMessage> | undefined;
  readonly onApprove?: (() => void) | undefined;
  readonly onDeny?: (() => void) | undefined;
};
```

Fallback copy reads `playbackMode`; layout reads `mode`. No child component should receive the complete `PresentationState` merely to inspect one field.

- [ ] **Step 6: Remove the unused agent `setBeat` vocabulary**

Modify:

- `web/apps/console/src/demo/agent/events.ts`
- `web/apps/console/src/demo/agent/tools.ts`
- affected tests

Remove `setBeat` from `PresentationToolAction`, `AgentToolName`, and `AGENT_TOOLS`. Remove its route switch case. `rg -n -F 'setBeat' web/apps/console/src` must return no matches.

- [ ] **Step 7: Run stage and route tests**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation src/demo/agent
```

Expected: all presentation and prepared-agent tests PASS.

- [ ] **Step 8: Commit stage recomposition**

```powershell
git add web/apps/console/src/presentation web/apps/console/src/demo/agent
git commit -m "feat: compose presentation from storyboard scenes"
```

---

### Task 4: Add discussion branches and Q&A entry points

**Files:**
- Create: `web/apps/console/src/presentation/DiscussionPanel.tsx`
- Create: `web/apps/console/src/presentation/DiscussionPanel.test.tsx`
- Create: `web/apps/console/src/presentation/DiscussionIndex.tsx`
- Create: `web/apps/console/src/presentation/DiscussionIndex.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Consumes: discussion catalog and reducer actions from Tasks 1-2.
- Produces: branch index, direct branch hash rendering, and exact return-to-origin behavior.

- [ ] **Step 1: Write failing discussion navigation tests**

```tsx
it("opens a positioning branch and returns to the exact originating beat", async () => {
  window.location.hash = "#scene/positioning/lda-position";
  render(<PresentationRoute />);

  await userEvent.click(screen.getByRole("button", { name: /open discussion topics/i }));
  await userEvent.click(screen.getByRole("button", { name: /hosted automation/i }));
  expect(window.location.hash).toBe("#discuss/hosted-automation");

  await userEvent.click(screen.getByRole("button", { name: /return to positioning/i }));
  expect(window.location.hash).toBe("#scene/positioning/lda-position");
});

it("uses the parent scene as return location for a directly linked branch", async () => {
  window.location.hash = "#discuss/mcp-agent-scale";
  render(<PresentationRoute />);
  await userEvent.click(screen.getByRole("button", { name: /return to positioning/i }));
  expect(window.location.hash).toBe("#scene/positioning/landscape");
});
```

- [ ] **Step 2: Run the route tests and verify failure**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/PresentationRoute.test.tsx
```

Expected: FAIL because discussion controls are not rendered.

- [ ] **Step 3: Implement DiscussionIndex and DiscussionPanel**

`DiscussionIndex` lists all branches grouped by parent scene. `DiscussionPanel` renders title, claim-class badge, evidence pointer, summary, and a return button. For `hosted-automation`, include this bounded copy:

```text
A future scheduler could trigger a workflow that launches a verified headless coding-agent command with a stored prompt. lda.chat does not implement that trigger or scheduler in the submitted scope.
```

For `mcp-agent-scale`, cite the two URLs from the storyboard spec and label both measurements `External context`.

- [ ] **Step 4: Wire discussion controls into the stage**

Add an unobtrusive `Open discussion topics` control for scenes with branches and a global `Q&A` control. Opening a branch dispatches `open_discussion`; closing dispatches `close_discussion`. Hash changes must continue to mirror reducer state.

- [ ] **Step 5: Run discussion and route tests**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/DiscussionPanel.test.tsx src/presentation/DiscussionIndex.test.tsx src/presentation/PresentationRoute.test.tsx
```

Expected: all focused tests PASS.

- [ ] **Step 6: Commit discussion branches**

```powershell
git add web/apps/console/src/presentation
git commit -m "feat: add presentation discussion branches"
```

---

### Task 5: Add presenter controls, appearance overrides, and chat dock

**Files:**
- Create: `web/apps/console/src/presentation/PresenterControls.tsx`
- Create: `web/apps/console/src/presentation/PresenterControls.test.tsx`
- Create: `web/apps/console/src/presentation/ChatDock.tsx`
- Create: `web/apps/console/src/presentation/ChatDock.test.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.tsx`
- Modify: `web/apps/console/src/presentation/OperatorChat.test.tsx`
- Modify: `web/apps/console/src/presentation/PresentationRoute.tsx`
- Modify: `web/apps/console/src/presentation/PresentationStage.tsx`

**Interfaces:**
- Consumes: reducer override and controls actions.
- Produces: hidden presenter toolbar, independent stage/chat theme overrides, dock preview/open behavior, and semantic control callbacks suitable for a later remote transport.

- [ ] **Step 1: Write failing controls and dock tests**

```tsx
it("changes stage and chat themes independently", async () => {
  render(<PresenterControls {...props} />);
  await userEvent.selectOptions(screen.getByLabelText(/stage theme/i), "night");
  await userEvent.selectOptions(screen.getByLabelText(/chat theme/i), "light");
  expect(props.setStageTheme).toHaveBeenCalledWith("night");
  expect(props.setChatTheme).toHaveBeenCalledWith("light");
});

it("opens docked chat by click and keyboard", async () => {
  render(<ChatDock open={props.openChat} />);
  await userEvent.click(screen.getByRole("button", { name: /open agent chat/i }));
  expect(props.openChat).toHaveBeenCalledTimes(1);
});

it("forces replay without changing the current presentation location", async () => {
  render(<PresenterControls {...props} />);
  await userEvent.click(screen.getByRole("button", { name: /force replay fallback/i }));
  expect(props.forceReplay).toHaveBeenCalledTimes(1);
  expect(props.jump).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation/PresenterControls.test.tsx src/presentation/ChatDock.test.tsx
```

Expected: FAIL because both components are missing.

- [ ] **Step 3: Implement PresenterControls**

The toolbar opens with `P` and closes with `Escape`. It exposes:

- previous and next;
- scene jump;
- current scene and beat;
- stage theme override: `scene default`, `paper`, `night`;
- chat theme override: `scene default`, `light`, `dark`;
- chat mode override: `scene default`, `hidden`, `full`, `rail`, `dock`;
- replay/live status and force replay;
- open discussion index;
- reset overrides.

Keep these as callback props; do not introduce networking or global stores.
`forceReplay` calls `demo.setMode("replay")`, restores replay evidence when live
evidence is absent, and does not dispatch a navigation action. This is the
manual live-failure fallback and must preserve the current scene and beat.

- [ ] **Step 4: Implement the chat dock**

When composition is `dock`, `OperatorChat` is visually hidden and `ChatDock` renders in the lower-left corner. Hover or focus shows a compact preview; click, `Enter`, or `Space` dispatches a chat mode override to `rail`. The dock button must remain visible against both stage themes.

- [ ] **Step 5: Update route keyboard behavior**

Maintain the existing editable-target guard. Add `P` for presenter controls. `Escape` uses reducer overlay priority. Do not bind global shortcuts while focus is inside a button, input, select, textarea, or content-editable element.

- [ ] **Step 6: Run controls, route, and chat tests**

Run:

```powershell
pnpm --dir web --filter @lda/console exec vitest run src/presentation
```

Expected: all presentation tests PASS.

- [ ] **Step 7: Commit presenter controls**

```powershell
git add web/apps/console/src/presentation
git commit -m "feat: add presentation controls and chat dock"
```

---

### Task 6: Enforce the 720p no-scroll composition

**Files:**
- Modify: `web/apps/console/src/presentation/presentation.css`
- Modify: `web/apps/console/src/presentation/PresentationRoute.test.tsx`

**Interfaces:**
- Consumes: stable region markup and data attributes from Tasks 3 and 5.
- Produces: viewport-bound layout and theme tokens; no JavaScript layout measurements.

- [ ] **Step 1: Add structural assertions before CSS changes**

```tsx
it("renders stable chat, primary, evidence, and navigation regions", () => {
  render(<PresentationRoute />);
  expect(screen.getByLabelText(/agent chat region/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/primary presentation region/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/evidence region/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/presentation scene rail/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Replace the vertically stacked CSS with a viewport grid**

Use these layout invariants:

```css
.presentation-route {
  height: 100dvh;
  min-height: 0;
  overflow: hidden;
}

.presentation-stage {
  height: 100dvh;
  min-height: 0;
  display: grid;
  grid-template:
    "chat primary evidence" minmax(0, 1fr)
    "rail rail rail" auto /
    var(--chat-width) minmax(0, 1fr) var(--evidence-width);
}

.presentation-stage__chat,
.presentation-stage__primary,
.presentation-stage__evidence {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
```

Derive `--chat-width` and `--evidence-width` from data attributes. Only chat message history, raw evidence, and oversized code blocks may scroll internally. The document and primary stage may not scroll. Use existing font variables and add paper/night tokens under `[data-stage-theme]`; do not restyle `/console`.

- [ ] **Step 3: Keep motion purposeful and bounded**

Add transitions only for grid widths, opacity, and transform on chat/evidence/primary regions. Duration must be 180-600ms. Preserve the existing `prefers-reduced-motion` override.

- [ ] **Step 4: Run unit tests and build**

Run:

```powershell
pnpm --dir web --filter @lda/console test
pnpm --dir web --filter @lda/console typecheck
pnpm --dir web --filter @lda/console build
```

Expected: console tests PASS, typecheck exits 0, build exits 0.

- [ ] **Step 5: Run the 1280x720 browser smoke**

Start the existing development server in a separate terminal:

```powershell
pnpm --dir web dev
```

Then use the installed Playwright CLI:

```powershell
pnpx @playwright/cli@latest open http://127.0.0.1:5173/present
pnpx @playwright/cli@latest resize 1280 720
pnpx @playwright/cli@latest eval "({scrollHeight: document.documentElement.scrollHeight, innerHeight: window.innerHeight, hash: location.hash})"
pnpx @playwright/cli@latest screenshot --filename=.playwright-cli/defense-storyboard-1280x720.png
```

Expected: `scrollHeight` equals `innerHeight`; the screenshot shows the active scene without graph, controls, or navigation below the fold. Advance through all main beats with `ArrowRight`, open one discussion branch, return, open the chat dock, and verify `/console` still renders.

- [ ] **Step 6: Commit the viewport composition**

```powershell
git add web/apps/console/src/presentation
git commit -m "style: fit defense compositor to 720p"
```

---

### Task 7: Document the compositor and run regression verification

**Files:**
- Modify: `web/README.md`
- Modify: `docs/current_roadmap.md`
- Move after completion: `docs/superpowers/plans/2026-07-04-defense-storyboard-compositor.md` to `docs/historical/superpowers/plans/2026-07-04-defense-storyboard-compositor.md`

**Interfaces:**
- Consumes: completed route behavior.
- Produces: operator instructions and accurate roadmap state.

- [ ] **Step 1: Update web documentation**

Document:

- `/present` and canonical `#scene/<scene>/<beat>` hashes;
- `#discuss/<branch>` hashes;
- arrow, space, escape, and `P` controls;
- replay-first startup;
- chat dock behavior;
- scene-default and rehearsal theme overrides;
- 1280x720 target;
- explicit deferral of AI Elements, live LLM, remote phone control, and final visual polish.

- [ ] **Step 2: Update the live roadmap**

Mark the storyboard compositor slice completed and add the next two slices in order:

1. adopt source-owned AI Elements chat primitives against existing `AgentMessagePart` / `AgentDriver` contracts;
2. implement final scene visuals, motion choreography, evidence assets, and rehearsal timing.

- [ ] **Step 3: Run focused and full web verification**

Run:

```powershell
pnpm --dir web test
pnpm --dir web typecheck
pnpm --dir web build
git diff --check
```

Expected: all web tests PASS, all workspace typechecks exit 0, build exits 0, and `git diff --check` reports no whitespace errors.

- [ ] **Step 4: Search for stale flat-beat vocabulary**

Run:

```powershell
rg -n 'presentationBeats|BeatId|beatFromHash|hashForBeat|setBeat|#interrupt-approval|#trace-evidence' web docs/current_roadmap.md web/README.md
```

Expected: no live-code or live-doc matches. Historical documentation may retain old vocabulary.

- [ ] **Step 5: Archive the completed plan and commit documentation**

```powershell
git mv docs/superpowers/plans/2026-07-04-defense-storyboard-compositor.md docs/historical/superpowers/plans/2026-07-04-defense-storyboard-compositor.md
git add web/README.md docs/current_roadmap.md docs/historical/superpowers/plans/2026-07-04-defense-storyboard-compositor.md
git commit -m "docs: record defense compositor completion"
```

## Self-Review Checklist

- [ ] The plan implements every main-story acceptance criterion except deliberately deferred chat replacement, live LLM, remote control, and final polish.
- [ ] All 12 scenes and five discussion branches have exact ids and evidence metadata.
- [ ] Scene/beat hashes have one canonical grammar and invalid hashes fail closed to the first scene.
- [ ] Prepared replay, approval, graph, operation, and evidence paths remain in the route.
- [ ] No task introduces a second transport, state store, or component runtime.
- [ ] No task preserves unused flat-beat compatibility behavior.
- [ ] Each task ends in focused verification and a reviewable commit.

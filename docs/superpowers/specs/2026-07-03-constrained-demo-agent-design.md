# Constrained Demo Agent Design

## Status

Current design contract for the next Workflow Console slice.

## Related Documents

- [Workflow console, agent demo, and defense presentation](2026-07-01-workflow-console-agent-demo.md)
- [Demo autoplay and replay](2026-07-03-demo-autoplay-replay.md)
- [React presentation mode](2026-07-03-react-presentation-mode-design.md)
- [React presentation mode before Astro](../../adr/0003-react-presentation-mode-before-astro.md)
- [Workflow Console product contract](../../../web/apps/console/PRODUCT.md)

## Purpose

The presentation route currently has replay and live workflow execution, but the
operator chat is still mostly a fixed narrative. The next slice adds a
constrained demo agent: a small recipe runner that can narrate and invoke one
prepared workflow path without pretending to be a general autonomous planner.

The goal is to make the defense story sharper:

- the operator asks for the thesis readiness report;
- the prepared agent selects the known report-workflow recipe;
- the agent emits visible tool-call events for workflow operations;
- each tool call maps to real replay/live evidence;
- the graph, interrupt, output, trace, and evidence surfaces remain the main
  proof.

This is not a free-form LLM agent. It is a deterministic macro with an
agent-shaped event stream.

## Product Boundary

The demo agent may say what it is doing and may invoke the prepared workflow
recipe. It must not claim to plan arbitrary workflows, inspect arbitrary user
files, or choose unknown tools.

Allowed language:

- "Prepared recipe"
- "Constrained demo agent"
- "I will call the workflow substrate"
- "This tool call maps to `workflow.runs.start`"

Avoid:

- "Autonomous agent"
- "I designed the workflow from scratch"
- "I can operate any workspace task"
- "Model decided"

If a later live LLM is added, the UI copy must still distinguish the model's
proposal from the workflow substrate's execution and evidence records.

## Driver Boundary

Introduce an explicit driver boundary so the prepared recipe and a future LLM
driver can feed the same presentation UI.

```ts
type AgentDriverKind = "prepared-recipe" | "ai-sdk";

type AgentMessageEvent =
  | AgentTextEvent
  | AgentToolCallEvent
  | AgentToolResultEvent
  | AgentApprovalRequestEvent
  | AgentFailureEvent;

type AgentDriver = {
  readonly kind: AgentDriverKind;
  readonly start: (input: AgentRunInput) => AsyncIterable<AgentMessageEvent>;
};
```

The first implementation only ships the `prepared-recipe` driver. It produces
events from a hard-coded recipe and calls the existing demo timeline execution
path.

The `ai-sdk` kind is reserved for a future driver. The boundary should be shaped
so a server-side Vercel AI SDK integration can map `streamText` parts into the
same event union:

- text delta or final text -> `AgentTextEvent`;
- tool call -> `AgentToolCallEvent`;
- tool result -> `AgentToolResultEvent`;
- tool requiring user approval -> `AgentApprovalRequestEvent`;
- failed stream/tool/provider error -> `AgentFailureEvent`.

Do not add the AI SDK dependency in this slice unless the implementation plan
explicitly chooses to build the live LLM driver. The API-key boundary belongs on
the web server, not in the browser.

## Prepared Recipe

The first recipe is:

```text
prepare-thesis-report
```

It is bound to the existing `examples/lda_report_workflow/` deployment:

```text
lda_report_case_study.default
```

Recipe stages:

1. **User request**: "Prepare the thesis readiness report."
2. **Recipe selection**: agent identifies the prepared report workflow.
3. **Deployment check**: calls `workflow.deployments.inspect`.
4. **Run start**: calls `workflow.runs.start`.
5. **Typed review**: asks the operator to approve selected issues.
6. **Run resume**: calls `workflow.runs.resume`.
7. **Trace read**: calls `workflow.runs.trace`.
8. **Summary**: reports produced markdown, created issues, run id, and trace
   evidence.

Each stage produces an agent event, and operation stages must carry the same
operation metadata already used by `OperationBlock` and the evidence drawer.

## Architecture

Add a focused demo-agent module under the console app:

```text
web/apps/console/src/demo/agent/
  events.ts
  recipes.ts
  preparedRecipeDriver.ts
  useDemoAgent.ts
```

Responsibilities:

- `events.ts`: event union, ids, and small helpers.
- `recipes.ts`: declarative recipe metadata and copy.
- `preparedRecipeDriver.ts`: deterministic async generator that advances the
  recipe and delegates workflow work to the existing live/replay timeline path.
- `useDemoAgent.ts`: React hook that owns driver state, messages, current tool
  event, failure state, and reset/start controls.

Do not make `OperatorChat` own workflow execution. It should render agent
events passed to it.

Do not duplicate JSON-RPC calls. The driver should reuse the existing demo
timeline execution seam or a small extracted operation adapter from it.

## Data Flow

```text
PresentationRoute
  -> useDemoAgent(driver = preparedRecipe)
  -> PreparedRecipeDriver
  -> existing demo timeline live/replay operation path
  -> AgentMessageEvent[]
  -> OperatorChat / OperationBlock / EvidenceDrawer / DemoTimeline
```

In replay mode, the driver reads from the reviewed recording and emits the
matching agent events without a server.

In live mode, the driver calls the connected workflow server through the
existing RPC operation path. Live mode remains explicit and disabled without a
target.

## Future AI SDK Path

A future implementation can add:

```text
web/apps/server/src/agent/
  aiSdkDriver.ts
  workflowTools.ts
```

The server-side driver can use Vercel AI SDK APIs such as `streamText` with a
bounded tool set:

- `inspectDeployment`
- `startPreparedReportRun`
- `resumeIssueReview`
- `readRunTrace`

The UI should not need to know whether events came from the prepared driver or
an AI SDK stream. Both produce `AgentMessageEvent`.

Rules for the future LLM driver:

- server-side only for provider credentials;
- bounded tool set;
- maximum step count;
- no arbitrary workflow authoring in the defense demo path;
- explicit tool approval for human interrupt decisions;
- event stream must preserve raw/interpreted evidence links.

## Presentation Behavior

The operator chat becomes event-driven:

- user message is rendered from the recipe input;
- agent narration is rendered from `AgentTextEvent`;
- tool calls are rendered compactly in chat and can expand to `OperationBlock`;
- tool results link to the graph, trace, and evidence drawer;
- approval request focuses the existing typed review panel.

The existing hard-coded chat copy should be replaced only where the agent event
stream can supply equivalent copy. Keep the visual style unchanged in this
slice; style polish is deferred.

## Error Handling

Failure should be visible and bounded:

- missing deployment -> agent failure event with setup hint;
- RPC failure -> tool-result failure event with raw response when available;
- unexpected run status -> failure event naming the expected and actual status;
- user cancellation -> normal recipe completion with cancelled outcome, not an
  exception;
- disconnected live mode -> disable start and show "connect or switch to
  replay".

The recipe must stop after a failure. It should not retry or invent recovery
steps in this slice.

## Testing

Unit tests should cover:

- prepared recipe emits expected event order;
- prepared driver cannot emit operations outside the recipe;
- replay mode produces agent events without a target;
- live mode delegates to the operation path in the expected order;
- approval event pauses until selected issues are submitted or cancelled;
- reset/start clears stale messages, approvals, outputs, and in-flight work;
- `OperatorChat` renders text, tool call, tool result, and failure events.

Browser or component smoke should cover:

1. load `/present`;
2. start prepared agent in replay mode;
3. see recipe selection, run-start tool call, interrupt approval, resume, trace,
   and summary;
4. open an operation block from a chat/tool event;
5. switch to live mode without a target and see a disabled start state.

## Success Criteria

The slice is complete when:

1. presentation chat is driven by agent events instead of fixed static copy;
2. the prepared recipe can run fully in replay mode without a server;
3. live mode uses the existing workflow operation path and remains explicit;
4. tool-call events map to operation blocks and evidence records;
5. the code has a named driver seam for a future AI SDK implementation;
6. no AI provider key or model dependency is required for the prepared demo;
7. copy clearly says this is a constrained recipe, not a general autonomous
   planner.

## Out Of Scope

- Adding Vercel AI SDK as a dependency.
- Building a generic chat composer.
- Free-form workflow authoring from natural language.
- Provider selection UI.
- Persisting agent sessions.
- Re-styling the presentation.
- Replacing the lifecycle explorer.

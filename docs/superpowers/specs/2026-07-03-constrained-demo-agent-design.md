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
standard AI-app-shaped chat/event surface backed first by a constrained demo
agent: a small prepared driver that can narrate, invoke one prepared workflow
path, and control presentation focus without pretending to be a general
autonomous planner.

The goal is to make the defense story sharper:

- the operator asks for the thesis readiness report;
- the prepared agent selects the known report-workflow recipe;
- the agent emits visible tool-call events for workflow operations;
- the agent can emit presentation tool calls such as selecting a graph node;
- each tool call maps to real replay/live evidence;
- the graph, interrupt, output, trace, and evidence surfaces remain the main
  proof.

This is not a free-form LLM agent. It is a deterministic macro with an
AI-chat-compatible event stream.

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
driver can feed the same standard chat/presentation UI.

```ts
type AgentDriverKind = "prepared-recipe" | "ai-sdk";

type AgentApproval = { readonly approved: boolean; readonly comment: string };

type AgentDriver = {
  readonly kind: AgentDriverKind;
  readonly run: (
    input: AgentRunInput,
    signal: AbortSignal,
    requestApproval: () => Promise<AgentApproval>,
  ) => AsyncIterable<AgentMessage>;
};
```

The first implementation only ships the `prepared-recipe` driver. It produces
events from a hard-coded recipe, calls the existing demo timeline execution
path, and emits presentation actions through the same event stream. The
prepared driver ignores the `requestApproval` callback (deterministic, no
approval needed).

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

## Chat Surface

The chat should look and behave like a standard modern AI application even when
the underlying driver is deterministic. It should have a normal message list,
assistant responses, compact tool-call parts, tool-result parts, failure parts,
and a clear disabled composer or preset prompt affordance.

The first slice should not invent a complex custom chatbot framework. It should
define the minimum message/part model that can later map to Vercel AI SDK UI
message parts:

```ts
type AgentMessagePart =
  | { readonly type: "text"; readonly text: string }
  | { readonly type: "tool-call"; readonly call: AgentToolCall }
  | { readonly type: "tool-result"; readonly result: AgentToolResult }
  | { readonly type: "presentation-action"; readonly action: PresentationToolAction }
  | { readonly type: "error"; readonly message: string };
```

The UI must not care whether parts came from the prepared driver or a future AI
SDK stream. In the prepared driver, messages may appear as complete messages
with a short fade. No slow typewriter effect is required.

## Tool Taxonomy

Separate tools into two families.

**Workflow tools** call or replay workflow substrate operations:

- `inspectDeployment` -> `workflow.deployments.inspect`
- `startPreparedReportRun` -> `workflow.runs.start`
- `resumeIssueReview` -> `workflow.runs.resume`
- `readRunTrace` -> `workflow.runs.trace`

**Presentation tools** control the stage only:

- `selectWorkflowNode({ nodeId })`
- `focusOperation({ eventId })`
- `openEvidence({ eventId })`
- `showTraceFrame({ frameIndex })`
- `setBeat({ beatId })`

Presentation tools are important because they model the interaction the future
agent should have with the visual product. For example, the user or scripted
agent can say "let's zoom into the interrupt node", which becomes:

```text
tool: selectWorkflowNode
input: { "nodeId": "review_issues" }
```

The tool result is not workflow evidence; it is stage state. The UI should label
it accordingly so viewers do not confuse visual focus with workflow execution.

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
operation metadata already used by `OperationBlock` and the evidence surface.

## Architecture

Add a focused demo-agent module under the console app:

```text
web/apps/console/src/demo/agent/
  events.ts
  tools.ts
  recipes.ts
  preparedRecipeDriver.ts
  useDemoAgent.ts
```

Responsibilities:

- `events.ts`: chat-compatible message and event union, ids, and small helpers.
- `tools.ts`: workflow-tool and presentation-tool descriptors, including the
  finite allowed tool names.
- `recipes.ts`: declarative recipe metadata and copy.
- `preparedRecipeDriver.ts`: deterministic async generator that advances the
  recipe, delegates workflow work to the existing live/replay timeline path, and
  emits presentation actions.
- `useDemoAgent.ts`: React hook that owns driver state, messages, current tool
  event, failure state, and reset/start controls.

Do not make `OperatorChat` own workflow execution. It should render agent
events passed to it.

Do not duplicate JSON-RPC calls. The driver should reuse the existing demo
timeline execution seam or a small extracted operation adapter from it.

Do not let workflow tools mutate presentation state directly. A workflow tool
produces operation evidence. A presentation tool produces stage actions.

## Effect Boundary

The project already uses `effect` and `@effect/rpc` in `web/packages/rpc`.
The console app currently uses React hooks plus Valibot decoders. This slice may
introduce Effect for the demo-agent runtime, but it should do so at the driver
boundary rather than inside render components.

Recommended split:

- pure recipe/event types stay ordinary TypeScript;
- workflow and presentation tool execution can return `Effect` values;
- the prepared driver can expose an `AsyncIterable<AgentMessageEvent>` adapter
  for React while using Effect internally;
- React hooks run the driver at the edge and translate emitted events into
  component state.

This keeps the future AI SDK path clean. A server-side AI SDK driver can use
Effect for bounded tool execution, typed errors, cancellation, and evidence
recording, while the React chat UI still consumes the same event stream.

Do not add Effect ceremony to static render components. Use Effect where it
buys typed tool execution, cancellation, dependency injection, or testable
driver composition.

## Data Flow

```text
PresentationRoute
  -> useDemoAgent(driver = preparedRecipe)
  -> PreparedRecipeDriver
  -> PresentationToolAdapter -> selected node / beat / evidence state
  -> AgentMessage[]
  -> StandardChat / OperationBlock / EvidenceDrawer / DemoTimeline
```

The prepared driver reads from the reviewed recording and emits agent events
without a server. It passes operation evidence to the hook, which forwards it
to the evidence surface.

In live mode, the driver calls the connected workflow server through the
existing RPC operation path. Live mode is deferred to a future slice; the
prepared driver is replay-only for now. The `AgentDriver` interface includes
`requestApproval` for future live-mode approval, but the prepared driver
currently ignores it.

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
- `selectWorkflowNode`
- `openEvidence`

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

The operator chat becomes a standard event-driven chat:

- user message is rendered from the recipe input;
- agent narration is rendered from `AgentTextEvent`;
- workflow tool calls are rendered compactly in chat and can expand to
  `OperationBlock`;
- presentation tool calls are rendered compactly in chat and update the stage;
- tool results link to the graph, trace, and evidence inspector;
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
- prepared driver cannot emit presentation actions outside the allowed tool set;
- replay mode produces agent events without a target;
- presentation tool events select the expected workflow node or evidence target;
- approval event pauses until selected issues are submitted or cancelled;
- reset/start clears stale messages, approvals, outputs, and in-flight work;
- `OperatorChat` renders text, tool call, tool result, and failure events.

Browser or component smoke should cover:

1. load `/present`;
2. start prepared agent in replay mode;
3. see recipe selection, run-start tool call, interrupt approval, resume, trace,
   and summary;
4. trigger or replay `selectWorkflowNode({ nodeId: "review_issues" })` and see
   the graph spotlight move to the interrupt node;
5. open an operation block from a chat/tool event;
6. switch to live mode without a target and see a disabled start state.

## Success Criteria

The slice is complete when:

1. presentation chat is driven by agent events instead of fixed static copy;
2. the prepared recipe can run fully in replay mode without a server;
3. live mode is deferred; the prepared driver is replay-only;
4. tool-call events map to operation blocks and evidence records;
5. presentation tool events can focus the graph/evidence stage;
6. the code has a named driver seam for a future AI SDK implementation;
7. no AI provider key or model dependency is required for the prepared demo;
8. copy clearly says this is a constrained recipe, not a general autonomous
   planner.

## Out Of Scope

- Adding Vercel AI SDK as a dependency.
- Building a generic chat composer.
- Free-form workflow authoring from natural language.
- Provider selection UI.
- Persisting agent sessions.
- Re-styling the presentation.
- Replacing the lifecycle explorer.
- Live mode: the prepared driver is replay-only for now. Live mode uses the
  existing workflow operation path and remains explicit.

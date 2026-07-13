# lda.chat Workflow Console

A local React console for inspecting workflow JSON-RPC servers. Connects to a
loopback `wf-rpc-server` through a Hono proxy, displays source inventory and
raw protocol evidence.

## Quick Start

```powershell
# Terminal 1: workflow JSON-RPC server
uv run wf-rpc-server --config wf.config.json --host 127.0.0.1 --port 8765

# Terminal 2: development (Vite + Hono)
pnpm --dir web install
pnpm --dir web dev
```

Open `http://127.0.0.1:5173` in the browser. Paste the target URL:

```text
http://127.0.0.1:8765/rpc
```

Click **Connect**. The console will:

1. Validate the target is a loopback address
2. Call `workflow.health` on the upstream server
3. Display connection status and source inventory
4. Show raw protocol evidence for each operation

## Production Build

```powershell
pnpm --dir web build
pnpm --dir web start
```

A single Hono process serves the built React application and API routes from
`http://127.0.0.1:8787`.

## Commands

| Command | Description |
|---------|-------------|
| `pnpm --dir web install` | Install all workspace dependencies |
| `pnpm --dir web dev` | Start Vite + Hono development servers |
| `pnpm --dir web test` | Run all test suites |
| `pnpm --dir web typecheck` | Run TypeScript type checking |
| `pnpm --dir web build` | Build the React console for production |
| `pnpm --dir web start` | Start the production Hono server |

## Architecture

```text
web/
  apps/
    console/    React + Vite frontend
    server/     Hono local server (API + static serving)
  packages/
    rpc/        Effect-based JSON-RPC client, schemas, and errors
```

The browser communicates with Hono at `/api/connect` and `/api/rpc`. Hono
validates targets against loopback policy, executes typed JSON-RPC calls
through Effect, and returns plain JSON DTOs to the browser.

## Product And Design Context

The console app carries two design-context files:

- [`apps/console/PRODUCT.md`](apps/console/PRODUCT.md) captures the strategic
  product contract: users, purpose, personality, anti-references, and design
  principles.
- [`apps/console/DESIGN.md`](apps/console/DESIGN.md) captures the current visual
  system: tokens, typography, components, elevation, and do/don't rules.

This structure comes from the local Impeccable design workflow. `PRODUCT.md`
uses its product-register format, and `DESIGN.md` follows the DESIGN.md
convention: YAML frontmatter for machine-readable tokens, followed by six fixed
sections (`Overview`, `Colors`, `Typography`, `Elevation`, `Components`, and
`Do's and Don'ts`). Future UI work should read these files before changing
visual direction.

## Lifecycle Explorer

After connecting, the console displays the lifecycle explorer with three
columns: artifacts, deployments, and runs. Selecting a record loads its detail
view.

- **Artifacts**: list and inspect workflow artifacts with plan graph visualization
- **Deployments**: list and inspect deployments with validation status
- **Runs**: list and inspect runs with interrupt details, trace frames, and
  execution timeline
- **Graph**: `@xyflow/react` DAG visualization of the artifact plan, powered by
  `@dagrejs/dagre` layout
- **Evidence**: raw JSON-RPC request/response evidence with equivalent CLI text
- **Pagination**: Load more for artifact and run lists when cursors are available

## Security

- Only loopback targets are accepted (`127.0.0.1`, `localhost`, `[::1]`)
- Upstream redirects are rejected
- Request bodies are limited to 256 KiB
- Response bodies are limited to 4 MiB
- The server binds to `127.0.0.1` by default

## Smoke Test

With the Python server running, verify in the browser:

1. The initial page makes no upstream request
2. Connect succeeds against `http://127.0.0.1:8765/rpc`
3. Source rows appear after connection
4. Raw health and source-list exchanges are selectable in the evidence inspector
5. Equivalent CLI text is visible
6. `http://example.com:8765/rpc` is rejected without upstream fetch
7. Stopping the Python server produces the unreachable state while preserving
   the entered URL
8. Artifact, deployment, and run lists populate in the lifecycle explorer
9. Selecting an artifact shows its plan graph and detail panel
10. Selecting a run shows trace frames and interrupt details
11. Clicking a trace frame shows resolved input and output

### LDA Report Workflow Smoke

```powershell
# Terminal 1: start the workflow server with the report example
uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765

# Terminal 2: start the console dev server
pnpm --dir web dev
```

Connect to `http://127.0.0.1:8765/rpc`. The smoke passes when artifact list,
deployment list, run list, graph visualization, trace frames, and raw evidence
are all visible.

## lda Report Workflow Demo

Start the prepared workflow RPC server from the repository root:

```powershell
uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765
```

Start the web console:

```powershell
pnpm --dir web dev
```

Open `http://127.0.0.1:5173/`, connect to
`http://127.0.0.1:8765/rpc`, then use the `lda report workflow demo`
panel. The panel expects `lda_report_case_study.default` to already exist
in the connected store. If it is missing, the panel displays the exact
product CLI setup commands.

### Demo Timeline Modes

- **Live** executes the prepared deployment through public JSON-RPC calls.
- **Replay** uses the committed `lda-report-success-v1` recording and does not
  contact the workflow server during playback.

`Start presentation` begins autoplay. `Pause` stops before the next
operation, and `Next` applies exactly one operation or recorded event.
Playback always stops at `issue_review`; approval remains a human action in
both modes. Replay is visibly labeled and does not create real issues.

### Presentation Mode

The console exposes `/present`, a 720p no-scroll defense compositor for the
prepared `lda_report_workflow` story. It renders a 14-scene, multi-beat
storyboard (expanded from the original 12-scene defense plan; items 13 and 14
now cover evaluation and closing) with an adaptive aspect-ratio canvas, stable
stage regions, discussion branches, one editorial canvas, persistent scene-aware
assistant surfaces, and keyboard navigation.

The companion `/presenter` route is a read-only speech and Q&A reader. It uses
the same `#scene/<scene>/<beat>` and `#discuss/<branch>` hashes, shows target and
cumulative timing, keeps optional detail/evidence/Q&A collapsed, and links to
the corresponding audience slide in a new tab. It performs no workflow RPC,
replay, live-target, or cross-window synchronization. Use ArrowLeft and
ArrowRight to move between notes; covered checkboxes remain local to the page.
Must-say notes support authored inline Markdown emphasis for rapid scanning, and
the stable Previous/Next bar remains available at narrow viewport widths.

The final presentation beats frame the evaluation as bounded evidence, make
claim boundaries and future work explicit, and end on the canonical defense
discussion index rather than a benchmark or generic conclusion.

Scenes 8 and 9 use the canonical prepared-authoring recording as their only
execution evidence. Scene 8 is a single full-screen chat-entry beat: its
prefilled request is submitted locally, then reveals the first deterministic
user, assistant, and Discover tool group. It is deterministic replay, not a live
LLM chat, and does not start a workflow run. Scene 9 breaks the prepared
authoring into five phases with a persistent prepared-agent assistant pane on
the left and a dominant phase canvas on the right. The adaptive split starts
near 35/65 and keeps the matching prepared tool group synchronized with each
factual source, graph, repair, artifact, or deployment view. Neither scene calls
workflow authoring RPC operations — they consume deterministic prepared data. Scenes 10 through
12 use the canonical replay by default when no live target is available. When
the resolved target is healthy, the same prepared run flow can execute through
the public JSON-RPC operations and record live evidence using the same
DemoRunFacts projection. Raw protocol payloads are available through the
evidence receipt and inspector.

Scenes 8–12 share one compact footer demo rail. Scene 8 remains a local scripted conversation, with its chat composer as the main surface, while the rail owns `Run prepared workflow`, replay fallback, retry, running, paused, resuming, and completed labels.
With a healthy target, the rail starts the live chain through the existing
`/api/rpc` proxy; when health fails, it keeps `Play replay walkthrough` as an
explicit fallback. The presentation does not silently replace a live failure
with recorded evidence.

For local live rehearsal, run both services:

```powershell
pnpm --dir web dev
uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765
```

The browser runs on `5173`, the console server proxy runs on `8787`, and the
workflow RPC server listens on `8765/rpc`.

The presentation chat surface is source-owned and follows the AI Elements
conversation/message/tool/prompt-action model. It currently renders the
prepared timeline agent and approval flow; a future AI SDK driver should target
`AgentMessagePart` / `TimelineAgent`-compatible events instead of replacing the
presentation timeline.

The key deep-link-addressable defense states include:

- `/present#scene/agent-handoff/request` — Scene 8, prepared authoring request
- `/present#scene/prepared-lifecycle/discover` — Scene 9, discover phase
- `/present#scene/prepared-lifecycle/draft` — Scene 9, draft phase
- `/present#scene/prepared-lifecycle/deployment` — Scene 9, deployment phase
- `/present#scene/run-from-deployment/operation` — Scene 10, run operation
- `/present#scene/run-from-deployment/graph` — Scene 10, workflow graph
- `/present#scene/typed-human-boundary/approval` — Scene 11, typed approval
- `/present#scene/resume-output-evidence/resume` — Scene 12, resume proof

Legacy aliases from the earlier 12-scene plan (such as `workflow-demo` and
`interrupt-evidence`) are replaced by the IDs above and no longer resolve.

Scene 12 is factual by design. It projects the reviewed/live run into visible
workflow input, interrupt payload, resume decision, output, and trace facts.
Empty trace frame objects are shown as captured empty objects; absent fields are
called out as not captured rather than replaced by generic placeholders.

```powershell
pnpm --dir web dev
# open http://127.0.0.1:5173/present
```

#### Navigation

- **ArrowRight / Space**: advance to the next beat within a scene, then to the
  next scene
- **ArrowLeft**: rewind to the previous beat or scene
- **Escape**: close overlays in priority order (node spotlight, evidence, discussion)
- **P**: toggle presenter controls

#### Hash Format

- Main scenes: `#scene/<scene-id>/<beat-id>`
- Discussion branches: `#discuss/<branch-id>`

Invalid hashes fall back to the first scene and beat.

#### Chat Modes

Chat is composed per-beat with four modes: `hidden`, `full`, `rail`, and `dock`.
When `dock` is active, a floating button in the lower-left corner expands the
chat to `rail`.

#### Presentation Canvas

The presentation uses one warm Editorial Canvas across all scenes. Dark
surfaces are local to product evidence such as chat, graphs, traces, and
terminal-style operation blocks; they are not whole-stage themes.

#### Discussion Branches

Five discussion branches exist under the positioning scene. Opening a branch
from the main scene saves the originating beat as the return location. Direct
hash links to `#discuss/<branch-id>` return to the parent scene's first beat.

#### Replay-First Startup

Replay is the default mode. The demo timeline auto-starts in replay using the
committed `lda-report-success-v1` recording. No RPC server is required.

#### Editorial Canvas

The presentation renders on an adaptive editorial canvas that derives its aspect
ratio from the browser viewport. The canvas fills the available viewport while
clamping its aspect ratio between 4:3 and 16:9. It intentionally avoids
`transform: scale(...)`: React Flow figures, popovers, and floating UI measure
DOM geometry, so the stage must expose real element positions instead of scaled
coordinates. No URL query parameters or local-storage settings control the
ratio.

Scene 6 uses a recursive Interactive Figure with expand/collapse and breadcrumb
navigation.

Key Scene 6 deep links:

- `/present#scene/architecture/client` — root architecture overview
- `/present#scene/architecture/runtime/focus/runtime-providers` — one level deep
- `/present#scene/architecture/runtime/focus/runtime-providers/configured-providers` — two levels deep

#### Figure Controls

- **Enter / click**: expand a child figure
- **Escape**: pop one focus level
- **Tab / arrows**: move focus between figure nodes without advancing the presentation
- **Breadcrumbs**: jump to any ancestor focus level

#### Evidence Presentation

Evidence availability never resizes the primary presentation region. Each beat
may request an evidence presentation state (`hidden`, `receipt`, or `inspector`),
and a global override can be set through the presentation tool. The state is
cleared on scene navigation (next, previous, jump) but preserved through
discussion transitions.

- **Receipt**: a compact bottom-row button showing the count and label of
  available evidence records. Clicking opens the inspector.
- **Inspector**: a centered modal dialog with `Interpreted` and `Raw` tabs, a
  record selector, and focus trapping. `Escape` closes the inspector.

#### Constraints

This plan deliberately defers:
- AI Elements / Vercel AI chat primitives
- Live LLM driver integration
- Remote phone control
- Final visual polish and motion choreography

### Constrained Demo Agent

`/present` includes a prepared agent recipe for the thesis readiness report.
The recipe is deterministic: it emits standard chat message parts, workflow tool
calls, and presentation tool actions without requiring a model provider key.

The current prepared recipe can:

- identify the `lda_report_case_study.default` workflow deployment;
- show tool calls for run start, resume, and trace read;
- focus the `review_issues` interrupt node through a presentation tool action;
- open evidence linked to the run trace.

This is intentionally not a general autonomous planner. A future server-side
Vercel AI SDK driver can feed the same message-part interface.

### Authoring Story (Scenes 8 and 9)

Scenes 8 and 9 are the prepared authoring story. They use deterministic data
from the committed `projectPreparedAuthoring()` recording and never call
workflow authoring RPC operations.

- **Scene 8 (Agent Request)**: a single full-screen deterministic chat entry that
  pre-fills the report-authoring request. Send is local presentation state and
  reveals the first prepared Discover tool group. This is not a live LLM chat
  or workflow run.
- **Scene 9 (Prepared Workflow Lifecycle)**: a five-phase lifecycle
  (discover, draft, validate, artifact, deployment) with a compact phase rail
  and one dominant factual product projection per beat. A persistent prepared
  assistant pane stays visible on the left while the phase canvas remains
  dominant on the right; the starting split is approximately 35/65 and adapts
  to the available width. Its active tool group follows the current beat. There
  is no lower chat dock, detached trace modal, or second transcript.

  One staged message box remains visible in every phase. Discover and Validate
  start empty with useful placeholders; Draft and Artifact use the exact next
  authoring prompts. Sending an edited Draft advances to Validate and preserves
  that text as the projected user turn; sending an edited Artifact does the
  same for Deployment. Deployment Send records only `Run request prepared for
  the next execution slice.` and makes no run or RPC request.

The authoring scenes consume deterministic prepared data and never call
workflow authoring RPCs. Scene 9 ends at the truthful run-request
handoff; Scenes 10–12 own run activation, typed approval, resume, output, and
trace evidence. No Scene 9 message submission starts a workflow run.

### Demo Climax (Scenes 8–12)

Scenes 8 through 12 are the demo climax. They keep a continuity rail visible
while the prepared replay moves from persisted workflow run, to typed human
interrupt, to resume/output/evidence. The rail and outcome panel are
presentation-only projections over the committed replay; they do not add live
backend dependencies.

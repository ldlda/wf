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
prepared `lda_report_workflow` story. It renders a 12-scene, multi-beat
storyboard with an adaptive aspect-ratio canvas, stable stage regions, discussion
branches, act themes, a chat dock, and keyboard navigation.

Scenes 8 through 10 use the canonical replay as their only execution evidence.
The handoff expands an interpreted run operation into the center stage, then
keeps one workflow graph mounted while execution reaches the typed interrupt
and approval boundary. Raw protocol payloads are available through the evidence
receipt and inspector.

The presentation chat surface is source-owned and follows the AI Elements
conversation/message/tool/prompt-action model. It currently renders the
prepared timeline agent and approval flow; a future AI SDK driver should target
`AgentMessagePart` / `TimelineAgent`-compatible events instead of replacing the
presentation timeline.

The key defense states are directly addressable:

- `/present#scene/workflow-demo/operation`
- `/present#scene/workflow-demo/graph`
- `/present#scene/workflow-demo/interrupt`
- `/present#scene/interrupt-evidence/approval`

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

#### Stage Themes

Stage themes change by act: `paper` for scenes 1-3 and 11-12, `night` for
scenes 4-10. Presenter controls allow overriding stage and chat themes
independently during rehearsal.

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

### Demo Climax (Scenes 9–10)

Scenes 9 and 10 are the demo climax. They keep a continuity rail visible while
the prepared replay moves from agent handoff, to persisted workflow run, to
typed human interrupt, to resume/output/evidence. The rail and outcome panel are
presentation-only projections over the committed replay; they do not add live
backend dependencies.

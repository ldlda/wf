# Defense Presentation Runbook

This runbook is for rehearsing and presenting the lda.chat thesis defense with
the React presentation route. It is intentionally operational: what to run,
what to open, what to say when something fails, and how the story should flow.
For a longer list of likely examiner questions, see
[`defense-qna.md`](defense-qna.md).

## One-Line Framing

The project began as an attempt to build an AI agent for creating workspace
automations. The implemented thesis contribution is the lower-level workflow
substrate that such agents need: typed workflow lifecycle, validation,
deployment binding, execution records, traces, source boundaries, and
interrupt/resume contracts.

Use this phrasing early if the title raises the question "Where is the AI
agent?":

> The title reflects the product goal. The submitted implementation focuses on
> the part that makes an agent useful and reliable: the workflow platform and
> tool surface that external agents such as Codex or Claude can operate.

## Story Spine

1. **Title / thesis.** Start with the AI-agent goal, then split the agent-shaped
   product into planner, tool surface, and workflow platform.
2. **Problem.** AI can lower the barrier to automation, but reusable automation
   still needs schemas, persistence, validation, traces, and recovery
   boundaries.
3. **Positioning.** Compare direct tool use, generated scripts, n8n/Zapier,
   Temporal, LangGraph, MCP, Codex-style coding, and scheduled agent products.
   The point is not that lda.chat replaces all of them; it occupies the typed
   workflow substrate niche for agent-operable workspace automation.
4. **Planner/runtime boundary.** External planners propose. The platform
   validates, persists, executes, records, and resumes.
5. **Lifecycle vocabulary.** Explain Draft, Artifact, Deployment, and Run in
   plain English before deep architecture.
6. **Architecture zoom.** Show client operations, API, runtime/providers, and
   NodeUse as nested figures.
7. **Authoring and repair.** Show why product surfaces matter: discovery,
   focused authoring commands, diagnostics, repair hints, and schema projection
   reduce the amount of guessing an agent has to do.
8. **Demo transition.** Let chat/product elements enter when the system becomes
   concrete. The chat is a product surface, not the whole thesis.
9. **Workflow demo.** Run or replay the report workflow through start,
   interrupt, approval/resume, trace, and output.
10. **Evaluation and limits.** Be explicit: 36 audited trials are engineering
    evidence, not a controlled model benchmark. The failures are part of the
    argument for better product surfaces.
11. **Future work.** The agent wrapper, scheduling, richer UI, security, and
    comparative studies are natural next layers, not claims already delivered.
12. **Close.** The thesis contribution is an agent-operable workflow substrate
    that separates planner uncertainty from deterministic runtime execution.

## Local Startup

Run these from the repository root.

### Presentation-Only Replay

Use this when you only need `/present`. It does not require the Python workflow
server because the presentation uses the committed replay.

```powershell
pnpm --dir web dev
```

Open:

```text
http://127.0.0.1:5173/present
```

### Console And Live Workflow Server

Use this when showing `/console` or live RPC-backed workflow operations.

Terminal 1:

```powershell
uv run wf-rpc-server --config examples/lda_report_workflow/wf.config.json --host 127.0.0.1 --port 8765
```

Terminal 2:

```powershell
pnpm --dir web dev
```

Open the console:

```text
http://127.0.0.1:5173/console
```

Connect to:

```text
http://127.0.0.1:8765/rpc
```

Open the presentation:

```text
http://127.0.0.1:5173/present
```

## Useful Deep Links

- Title: `http://127.0.0.1:5173/present#scene/thesis/title`
- Positioning: `http://127.0.0.1:5173/present#scene/positioning/landscape`
- Architecture root: `http://127.0.0.1:5173/present#scene/architecture/client`
- Runtime providers:
  `http://127.0.0.1:5173/present#scene/architecture/runtime/focus/runtime-providers`
- NodeUse:
  `http://127.0.0.1:5173/present#scene/architecture/node-use/focus/node-use`
- Demo operation:
  `http://127.0.0.1:5173/present#scene/workflow-demo/operation`
- Demo graph:
  `http://127.0.0.1:5173/present#scene/workflow-demo/graph`
- Interrupt preview:
  `http://127.0.0.1:5173/present#scene/workflow-demo/interrupt`
- Approval:
  `http://127.0.0.1:5173/present#scene/interrupt-evidence/approval`
- Trace/evidence:
  `http://127.0.0.1:5173/present#scene/interrupt-evidence/trace`
- Evaluation:
  `http://127.0.0.1:5173/present#scene/evaluation/cohort`

## Keyboard Controls

- `ArrowRight` or `Space`: advance one beat.
- `ArrowLeft`: go back one beat.
- `Escape`: close the top overlay: evidence inspector, node spotlight, or
  discussion branch.
- In interactive figures: `Tab` enters the current figure node, arrow keys move
  between nodes, `Enter` expands an expandable node, and `Escape` pops one
  figure focus level.

Avoid relying on undocumented shortcuts during the defense. If a control is not
visible or listed here, treat it as rehearsal-only.

## Live Demo Fallbacks

### If the web app is down

Say:

> The presentation is a React route served locally. If the development server
> fails, I can still explain the same architecture and evaluation from the PDF,
> because the thesis evidence is repository-backed and not dependent on this UI.

Then use the PDF and the deep-link list above as talking points.

### If the workflow RPC server is down

Say:

> The presentation demo uses a prepared replay by default, so the defense story
> does not depend on live network or model access. The live server shows the same
> product path when available.

Then continue with `/present`. Do not spend defense time debugging ports.

### If live RPC operations fail mid-demo

Say:

> This is why the thesis separates runtime evidence from planner behavior. A
> failed live operation remains observable as evidence, and the prepared replay
> lets me continue the same narrative without rewriting the result.

Then switch back to replay/deep-linked states.

### If asked why the demo is prepared

Say:

> The thesis evaluates the workflow substrate. The prepared demo is not evidence
> that an arbitrary model can plan perfectly; it is evidence that the platform
> can represent, validate, execute, interrupt, resume, and inspect a reusable
> workflow.

## Fifteen-Minute Timing

Target a 12-minute main path, leaving three minutes for questions.

| Time | Segment | Notes |
|---:|---|---|
| 0:00-1:00 | Title and framing | AI-agent goal -> workflow substrate contribution |
| 1:00-2:30 | Problem and positioning | Automation is hard; AI needs durable workflow contracts |
| 2:30-4:00 | Planner/runtime boundary | External planner proposes; platform owns execution |
| 4:00-5:30 | Lifecycle | Draft, artifact, deployment, run |
| 5:30-7:00 | Architecture zoom | Client/API/runtime/NodeUse |
| 7:00-8:30 | Authoring and repair | Discovery, schemas, diagnostics, repair hints |
| 8:30-10:30 | Demo | Start, interrupt, approval/resume, trace |
| 10:30-11:30 | Evaluation | 36 audited trials as bounded engineering evidence |
| 11:30-12:00 | Limits and future work | Agent wrapper, security, scheduling, comparative studies |
| 12:00-15:00 | Questions | Use prepared Q&A branches when available |

## Expected Hard Questions

### Where is the AI agent?

Answer:

> The autonomous planner is external. The thesis contribution is the substrate
> that makes an external agent's workflow output reusable and inspectable. That
> is why the system exposes CLI/JSON-RPC operations, typed schemas, diagnostics,
> deployments, runs, traces, and interrupt contracts.

### Is this better than LangGraph, n8n, Zapier, or Temporal?

Answer:

> The thesis does not claim global superiority. It positions lda.chat between
> direct agent tool use and conventional automation platforms: provider-neutral
> capabilities, typed workflow lifecycle, and agent-operable authoring surfaces.

### Does the 36-trial campaign prove model performance?

Answer:

> No. It is bounded engineering evidence about operability and UX failure modes.
> It is not a controlled benchmark, and the thesis says so.

### Is the security model production-ready?

Answer:

> No. The prototype enforces source boundaries and loopback web access for the
> demo, but production credentials, RBAC, tenant isolation, and untrusted-code
> execution are future work.

### What if the live demo fails?

Answer:

> The live demo is not the only evidence. The replay, tests, committed example,
> trace records, and thesis evaluation support the same claims.

## Pre-Defense Checklist

- Start `/present` once and walk through all main beats.
- Open Scene 6 root, runtime providers, and NodeUse deep links.
- Open Scene 9/10 demo deep links and verify evidence receipt/inspector.
- Confirm `Escape` closes overlays.
- Confirm the browser is at the intended zoom level and projector resolution.
- Keep the PDF available as a fallback.
- Keep the commands in this runbook available in a terminal or notes file.
